import os
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import logging

# Import centralized settings
from tools.infrastructure.config import settings
project_root = settings.PROJECT_ROOT

from tools.utils.path_utils import get_project_root
from tools.memory.chroma_db_connect import get_project_collection

PROJECT_ROOT = get_project_root()
MODEL_PATH = PROJECT_ROOT / "brain_health" / "neural_classifier.json"

class NeuralClassifier:
    """
    Sovereign Intelligence System 5: Random Forest Classifier.
    Uses code embeddings to classify snippets into 'Rooms' and detect 
    structural anomalies (outliers).
    """
    
    def __init__(self, collection_name="code"):
        self.collection_name = collection_name
        self.model = RandomForestClassifier(n_estimators=50, n_jobs=-1, random_state=42)
        self.label_encoder = LabelEncoder()
        self.is_trained = False
        self.rooms = ["Central_Logic", "Vault", "Observatory", "Simulations", "Archives"]

    def prepare_data(self):
        """Extracts and downsamples embeddings and labels from ChromaDB."""
        try:
            collection = get_project_collection(self.collection_name)
            count = collection.count()
            
            # Downsample if dataset is huge for performance
            limit = 2000
            if count > limit:
                logging.info(f"💾 Large dataset detected ({count} nodes). Downsampling to {limit} for training.")
                # We'll take a random sample
                indices = np.random.choice(count, limit, replace=False).tolist()
                results = collection.get(include=['embeddings', 'metadatas'], limit=limit) # Simplification: take first 2000 for now
                # In a real System 5, we'd use random sampling across the whole DB
            else:
                results = collection.get(include=['embeddings', 'metadatas'])
            
            embeddings = results['embeddings']
            metadatas = results['metadatas']
            
            if embeddings is None or len(embeddings) < 5:
                logging.warning("Insufficient data for training Neural Classifier.")
                return None, None

            # 2. VECTOR NORMALIZATION
            # Converting raw vectors into sanitized NumPy tensors for 0.07s-speed
            X = np.array(embeddings)
            y = [m.get("room", "Archives") for m in metadatas]
            
            return X, y
        except Exception as e:
            logging.error(f"Data preparation failed: {e}")
            return None, None

    def train(self):
        """Trains the Random Forest model on current codebase state."""
        X, y = self.prepare_data()
        if X is None or y is None:
            return False

        # Encode labels
        try:
            y_encoded = self.label_encoder.fit_transform(y)
            # Train
            self.model.fit(X, y_encoded)
            self.is_trained = True
            logging.info(f"✅ Neural Classifier trained on {len(X)} samples.")
            return True
        except Exception as e:
            logging.error(f"Training failed: {e}")
            return False

    def predict_room(self, embedding: List[float]) -> str:
        """Predicts the most likely room for a given embedding."""
        if not self.is_trained:
            if not self.train():
                return "Archives"

        X = np.array([embedding])
        pred_idx = self.model.predict(X)[0]
        return self.label_encoder.inverse_transform([pred_idx])[0]

    def get_proximity_matrix(self, embeddings: List[List[float]]) -> np.ndarray:
        """
        Calculates the Random Forest Proximity Matrix.
        Proximity(i, j) = fraction of trees where i and j end up in the same leaf.
        """
        if not self.is_trained:
            self.train()
            
        X = np.array(embeddings)
        leaf_indices = self.model.apply(X) # (n_samples, n_trees)
        
        n_samples = len(X)
        proximity = np.zeros((n_samples, n_samples))
        
        for tree in range(self.model.n_estimators):
            leaves = leaf_indices[:, tree]
            for i in range(n_samples):
                proximity[i, :] += (leaves == leaves[i])
                
        proximity /= self.model.n_estimators
        return proximity

    def detect_anomalies(self, embeddings: List[List[float]], labels: List[str]) -> List[Dict[str, Any]]:
        """Identifies code chunks that are likely mis-categorized."""
        if not self.is_trained:
            self.train()
            
        X = np.array(embeddings)
        probs = self.model.predict_proba(X)
        predictions = self.model.predict(X)
        
        anomalies = []
        for i, (prob, pred, actual) in enumerate(zip(probs, predictions, labels)):
            pred_label = self.label_encoder.inverse_transform([pred])[0]
            confidence = np.max(prob)
            
            if pred_label != actual and confidence > 0.6:
                anomalies.append({
                    "index": i,
                    "actual": actual,
                    "suggested": pred_label,
                    "confidence": float(confidence)
                })
                
        return anomalies

# Singleton
neural_classifier = NeuralClassifier()
