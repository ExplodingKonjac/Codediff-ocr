import utils.rich_tqdmpatch

import logging

from transformers import AutoModelForImageTextToText

from app.utils.rich_logging import RichLogManager

log_manager = RichLogManager(level=logging.INFO)

@log_manager.main_process
def main():
    model = AutoModelForImageTextToText.from_pretrained(
        "stepfun-ai/GOT-OCR-2.0-hf",
        device_map="auto",
    )
    logging.info("Device: %s", model.device)
    logging.info("Model architecture: %s", model)

    model.save_pretrained("./output/model")

if __name__ == "__main__":
    main()
