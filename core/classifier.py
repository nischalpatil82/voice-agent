"""
core/classifier.py — Enterprise Intent Classifier
LogisticRegression with calibrated probabilities for accurate confidence scoring.
Includes out-of-scope rejection and confidence-based fallback.
"""

import logging
import os
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from core.preprocessor import TextPreprocessor

LOG = logging.getLogger(__name__)


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class IntentClassifier:

    def __init__(self, training_data, confidence_threshold=0.35):
        if not training_data:
            raise ValueError("training_data must not be empty")

        self.preprocessor = TextPreprocessor()
        self.confidence_threshold = confidence_threshold
        self.log_predictions = _env_bool("VOICE_AGENT_LOG_PREDICTIONS", False)

        # Preprocess training data
        texts  = [self.preprocessor.preprocess(t) for t, _ in training_data]
        labels = [l for _, l in training_data]

        self.label_set = sorted(set(labels))

        from sentence_transformers import SentenceTransformer
        LOG.info("[ML] Loading SentenceTransformer 'all-MiniLM-L6-v2'...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = self.embedder.encode(texts)

        # Calibrated classifier for true probabilities
        base_clf = LogisticRegression(
            C=5.0,
            max_iter=2000,
            solver="lbfgs",
            class_weight="balanced",   # Handle imbalanced intent counts
        )
        
        # Adaptive cross-validation folds: use cv=2 if dataset is small, cv=3 otherwise
        cv_folds = 2 if len(texts) < 30 else 3
        
        self.model = CalibratedClassifierCV(base_clf, method="sigmoid", cv=cv_folds)

        self.model.fit(embeddings, labels)
        LOG.info(
            "[ML] Classifier trained - %s intents, %s examples, threshold=%s",
            len(self.label_set),
            len(texts),
            confidence_threshold,
        )

    def predict(self, text):
        """
        Predict intent with calibrated probability.
        Returns (intent, confidence) where confidence is a true probability [0, 1].
        If confidence < threshold, returns OUT_OF_SCOPE.
        """
        cleaned = self.preprocessor.preprocess(text)
        emb = self.embedder.encode([cleaned])

        # Get calibrated probabilities
        probabilities = self.model.predict_proba(emb)[0]
        best_idx      = np.argmax(probabilities)
        confidence     = round(float(probabilities[best_idx]), 4)
        intent        = self.model.classes_[best_idx]

        # Get top-3 for debugging
        top3_idx = np.argsort(probabilities)[-3:][::-1]
        top3 = [(self.model.classes_[i], round(float(probabilities[i]), 3))
                for i in top3_idx]
        if self.log_predictions:
            LOG.info("[ML] Input='%s' cleaned='%s' top3=%s", text, cleaned, top3)
        else:
            LOG.debug("[ML] top3=%s", top3)

        # Reject low confidence
        if confidence < self.confidence_threshold:
            LOG.debug("[ML] Low confidence (%s) -> OUT_OF_SCOPE", confidence)
            return "OUT_OF_SCOPE", confidence

        return intent, confidence

    def predict_top_n(self, text, n=3):
        """Return top N predictions with probabilities."""
        cleaned = self.preprocessor.preprocess(text)
        emb = self.embedder.encode([cleaned])
        probabilities = self.model.predict_proba(emb)[0]
        top_idx = np.argsort(probabilities)[-n:][::-1]
        return [(self.model.classes_[i], round(float(probabilities[i]), 4))
                for i in top_idx]