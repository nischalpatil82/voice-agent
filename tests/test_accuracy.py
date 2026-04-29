import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.justbill import intents
from projects.justbill import config
from core.classifier import IntentClassifier
from core.database import ItemDB
from core.matcher import ItemMatcher
from core.context import ConversationContext
from core.actions import ActionBuilder
from core.preprocessor import TextPreprocessor


# A small default test set if test_set.json is not provided
DEFAULT_TEST_SET = [
    {"text": "add to cart", "expected_intent": "ADD_TO_CART"},
    {"text": "show rings", "expected_intent": "SHOW_CATEGORY"},
    {"text": "what is the price", "expected_intent": "PRICE"},
    {"text": "remove it", "expected_intent": "REMOVE_ITEM"},
    {"text": "checkout now", "expected_intent": "CHECKOUT"},
    {"text": "i want to buy a diamond ring", "expected_intent": "ADD_TO_CART"},
    {"text": "any discounts", "expected_intent": "SHOW_OFFERS"},
    {"text": "buy diamond ring", "expected_intent": "ADD_TO_CART"},
    {"text": "show diamond ring", "expected_intent": "SEARCH"},
    {"text": "add this", "expected_intent": "ADD_TO_CART"},
    {"text": "open my orders", "expected_intent": "SHOW_ORDERS"},
    {"text": "show rings under 2 lakhs", "expected_intent": "FILTER"},
]


def run_evaluation():
    test_file = "test_set.json"
    if os.path.exists(test_file):
        with open(test_file, "r") as f:
            test_data = json.load(f)
    else:
        print(f"[{test_file}] not found. Using default dataset.")
        test_data = DEFAULT_TEST_SET

    print("Loading models...")
    start = time.time()
    
    db = ItemDB(config)
    db.load()
    matcher = ItemMatcher(db)
    
    reject_threshold = getattr(config, "CONFIDENCE_REJECT", 0.35)
    clf = IntentClassifier(intents.TRAINING_DATA, confidence_threshold=reject_threshold)
    
    preprocessor = TextPreprocessor()
    
    load_time = time.time() - start
    print(f"Models loaded in {load_time:.2f}s")
    print("-" * 50)
    
    correct = 0
    total = len(test_data)
    failed = []

    start = time.time()
    for item in test_data:
        text = preprocessor.preprocess(item["text"])
        intent, conf = clf.predict(text)
        
        expected = item["expected_intent"]
        if intent == expected:
            correct += 1
        else:
            failed.append({
                "original": item["text"],
                "cleaned": text,
                "predicted": intent,
                "expected": expected,
                "confidence": conf
            })
            
    eval_time = time.time() - start
    
    accuracy = correct / total if total > 0 else 0
    print(f"EVALUATION REPORT")
    print(f"Total phrases  : {total}")
    print(f"Correct        : {correct}")
    print(f"Accuracy       : {accuracy:.2%} ({(eval_time/total)*1000 if total > 0 else 0:.1f}ms/phrase)")
    print("-" * 50)
    
    if failed:
        print("FAILED SAMPLES:")
        for f in failed:
            print(f" Text: '{f['original']}' -> '{f['cleaned']}'")
            print(f" Pred: {f['predicted']} (Conf: {f['confidence']:.2f}) | Expected: {f['expected']}")
            print("")

if __name__ == "__main__":
    run_evaluation()
