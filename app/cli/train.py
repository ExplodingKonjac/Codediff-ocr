"""
Module including cli command train
"""
import logging
from dataclasses import dataclass

import click
import torch
import torch.nn.utils
from transformers import (
    AutoConfig, PreTrainedTokenizerBase, GotOcr2Processor, 
    GotOcr2ForConditionalGeneration, set_seed
)
from datasets import DatasetDict
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

from app.utils.rich_logging import RichLogManager

DEFAULT_DEVICE = (
    'cuda' if torch.cuda.is_available() else
    'xpu' if torch.xpu.is_available() else 'cpu'
)
SEED = 38567114
log_manager = RichLogManager(level=logging.INFO)


@dataclass
class _DataCollator:
    processor: GotOcr2Processor
    tokenizer: PreTrainedTokenizerBase
    device: str

    def __call__(self, batch: list[dict]) -> dict[str, torch.Tensor]:
        input_ids_list = []
        labels_list = []
        pixel_values_list = []

        for item in batch:
            prompt = self.processor(
                item['image'], format=True, return_tensors='pt'
            ).to(self.device)
            completion = self.tokenizer(
                item['text'] + '<|im_end|>', return_tensors='pt'
            ).to(self.device)

            input_ids_list.append(
                torch.concat([prompt['input_ids'][0], completion['input_ids'][0]])
            )
            labels_list.append(
                torch.concat([
                    torch.full_like(prompt['input_ids'][0], -100),
                    completion['input_ids'][0]
                ])
            )
            pixel_values_list.append(prompt['pixel_values'])

        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids_list, padding_value=self.tokenizer.pad_token_id, batch_first=True
        )
        attention_mask = input_ids.ne(self.tokenizer.pad_token_id)
        labels = torch.nn.utils.rnn.pad_sequence(
            labels_list, padding_value=-100, batch_first=True
        )
        pixel_values = torch.concat(pixel_values_list)
        pixel_values.requires_grad = True

        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels,
            'pixel_values': pixel_values,
        }


@click.command
@click.option('--base-model', 'base_model', type=str, default='stepfun-ai/GOT-OCR-2.0-hf')
@click.option('--dataset', 'dataset', type=click.Path(), required=True)
@click.option('--output', '-o', 'output', type=click.Path(), required=True)
@click.option('--device', 'device', type=str, default=DEFAULT_DEVICE)
@log_manager.main_process
def train(base_model: str, dataset: str, output: str, device: str):
    """
    Train the model.
    """
    logger = logging.getLogger('Main')

    logger.info("Loading base model (device=%s)...", device)
    config = AutoConfig.from_pretrained(base_model)
    config.text_config._attn_implementation = 'flash_attention_2'
    model = GotOcr2ForConditionalGeneration.from_pretrained(
        base_model,
        config=config,
        dtype=torch.bfloat16,
        device_map=device,
    )
    logger.info("Model architecture: %s", model)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    logger.info("Base model loaded. (device=%s)", device)

    logger.info("Loading processor...")
    processor = GotOcr2Processor.from_pretrained(base_model)
    logger.info("Processor loaded.")

    logger.info("Loading dataset...")
    ds = DatasetDict.load_from_disk(dataset)
    logger.info("Dataset loaded.")

    logger.info("Configuring trainer...")
    set_seed(SEED)
    data_collator = _DataCollator(
        processor=processor,
        tokenizer=processor.tokenizer,
        device=device,
    )
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.1,
        target_modules=[
            'q_proj', 'k_proj', 'v_proj', 'o_proj',
            'gate_proj', 'up_proj', 'down_proj'
        ],
        task_type='CAUSAL_LM'
    )
    training_args = SFTConfig(
        output_dir=output,
        num_train_epochs=3,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=4,
        bf16=True,
        fp16=False,
        learning_rate=5e-5,
        lr_scheduler_type='cosine',
        optim='adamw_bnb_8bit',
        weight_decay=0.01,
        warmup_ratio=0.1,
        save_total_limit=2,
        logging_steps=1,
        eval_steps=100,
        save_steps=100,
        remove_unused_columns=False,
        report_to='tensorboard',
        prediction_loss_only=True,
        gradient_checkpointing=True,
        dataloader_pin_memory=False
    )
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=ds['train'],
        eval_dataset=ds['val'],
        data_collator=data_collator,
        peft_config=lora_config
    )

    logger.info("Trainer configuration done. Start training.")
    trainer.train()

    logger.info("Training done, saving models...")
    trainer.save_model()
