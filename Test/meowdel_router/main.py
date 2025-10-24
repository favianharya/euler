import yaml
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification, logging
from typing import List
import re
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.set_verbosity_error()


def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

def estimate_complexity(prompt):
    length = len(prompt)
    multi = bool(re.search(r"\b(and|then|after|also)\b", prompt))
    instruction = bool(re.search(r"\b(why|how|explain|analyze|summarize|translate)\b", prompt, re.I))
    if length < 80 and not multi and not instruction:
        return "low"
    elif instruction or multi or 80 <= length <= 250:
        return "medium"
    return "high"

def estimate_length_type(prompt):
    return "short" if len(prompt) < 250 else "long"

class Model:
    def __init__(self, model_name):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)

    def _generate_classification(self, prompt, candidate_labels):
        classifier = pipeline("zero-shot-classification", model=self.model, tokenizer=self.tokenizer)
        return classifier(prompt, candidate_labels=candidate_labels)

    def classify_context(self, prompt, candidate_labels):
        return self._generate_classification(prompt, candidate_labels=candidate_labels)

    def classify_intent(self, prompt, candidate_labels):
        return self._generate_classification(prompt, candidate_labels=candidate_labels)


def main():
    ROUTING_MAP = read_yaml("yaml/routing_config.yaml")
    LABELS = read_yaml("yaml/labels.yaml")

    INTENT_LABELS = LABELS["intent_labels"]
    CONTEXT_LABELS = LABELS["context_labels"]

    model = Model(
        model_name="MoritzLaurer/deberta-v3-base-mnli",
    )

    prompt = """
    Below is an instruction that describes a task. Write a response that appropriately completes the request.

    ### Instruction:
    Give three tips for staying healthy.

    ### Response:
    1.Eat a balanced diet and make sure to include plenty of fruits and vegetables.
    2. Exercise regularly to keep your body active and strong.
    3. Get enough sleep and maintain a consistent sleep schedule.
    """

    intent_result = model.classify_intent(prompt, candidate_labels=INTENT_LABELS)
    intent = intent_result["labels"][0]

    context_result = model.classify_context(prompt, candidate_labels=CONTEXT_LABELS)
    context = context_result["labels"][0]

    complexity = estimate_complexity(prompt)
    length_type = estimate_length_type(prompt)

    try:
        selected_model = ROUTING_MAP[intent][context][f"{complexity}_{length_type}"]
    except KeyError:
        selected_model = ROUTING_MAP.get("default", "facebook/bart-large-mnli")

    print(f"🔎 Intent: {intent}")
    print(f"🌍 Context: {context}")
    print(f"⚙️ Complexity: {complexity}")
    print(f"📏 Length: {length_type}")
    print(f"→ Selected Model: {selected_model}")


if __name__ == "__main__":
    main()