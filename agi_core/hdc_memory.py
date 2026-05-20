import numpy as np
import time

class HDCMemory:
    """
    Hyperdimensional Computing (HDC) Memory Array.
    Implements true local, zero-power "metaplasticity" by projecting concepts
    into a 10,000-dimensional space and bundling them instantly.
    """
    def __init__(self, dim=10000):
        self.dim = dim
        self.item_memory = {} # Item string to bipolar vector mapping
        self.global_state = np.zeros(dim, dtype=np.int32)
        
    def _generate_random_vector(self):
        """Generates a bipolar vector (-1, 1)"""
        return np.random.choice([-1, 1], size=self.dim)
        
    def encode(self, concept: str) -> np.ndarray:
        """Fetch or create a base vector for a concept"""
        if concept not in self.item_memory:
            self.item_memory[concept] = self._generate_random_vector()
        return self.item_memory[concept]
        
    def bundle(self, vectors: list[np.ndarray]) -> np.ndarray:
        """
        Bundling (Addition) allows multiple concepts to coexist in a single vector.
        This is how we "instantly" add new markdown files to the global memory.
        """
        bundled = np.sum(vectors, axis=0)
        return np.where(bundled >= 0, 1, -1)
        
    def bind(self, v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
        """
        Binding (Element-wise multiplication in bipolar space).
        This connects two concepts logically (e.g., Key * Value, or Role * Filler).
        """
        return v1 * v2
        
    def update_memory(self, concepts: list[str]):
        """
        Simulates writing a new markdown file.
        Updates the global neural state instantly with zero tokens and zero power.
        """
        vecs = [self.encode(c) for c in concepts]
        doc_vector = self.bundle(vecs)
        # Update global state via bundling
        self.global_state = self.bundle([self.global_state, doc_vector])
        
    def query_similarity(self, concept: str) -> float:
        """
        Checks how heavily a concept is embedded in the global neural state.
        Cosine similarity over bipolar vectors.
        """
        if concept not in self.item_memory:
            return 0.0
        vec = self.item_memory[concept]
        # Dot product divided by dimensions gives similarity [-1, 1]
        sim = np.dot(vec, self.global_state) / self.dim
        return float(sim)

    def detect_bound_clusters(self, threshold=0.10) -> list:
        """
        [Flywheel] Reverses HDC vectors back into logic.
        Searches the memory for pairs of concepts that are strongly bound
        (their XOR'd vector is highly present in the global state).
        This signals they frequently co-occur or form a rule.
        """
        concepts = list(self.item_memory.keys())
        n = len(concepts)
        discovered_axioms = []
        
        for i in range(n):
            for j in range(i + 1, n):
                c1, c2 = concepts[i], concepts[j]
                # Avoid self-binding or trivial bindings
                if c1 == c2: continue
                
                v1 = self.item_memory[c1]
                v2 = self.item_memory[c2]
                bound_vec = self.bind(v1, v2)
                
                sim = float(np.dot(bound_vec, self.global_state) / self.dim)
                
                if sim > threshold:
                    discovered_axioms.append((c1, c2, sim))
                    
        # Sort by strongest binding
        discovered_axioms.sort(key=lambda x: x[2], reverse=True)
        return discovered_axioms

if __name__ == "__main__":
    print("--- HDC Metaplasticity Test ---")
    hdc = HDCMemory(dim=10000)
    
    # Simulate writing 1,000 markdown notes
    start_time = time.time()
    for i in range(1000):
        # A mix of generic words and a rare concept
        words = ["the", "finance", "model", f"note_{i}"]
        if i == 500:
            words.append("quantum_gravity")
        hdc.update_memory(words)
        
    duration = time.time() - start_time
    
    print(f"[HDC] Integrated 1,000 notes into continuous local memory in {duration:.4f} seconds.")
    print(f"[HDC] 'the' (highly frequent) similarity: {hdc.query_similarity('the'):.3f}")
    print(f"[HDC] 'quantum_gravity' (rare) similarity: {hdc.query_similarity('quantum_gravity'):.3f}")
    print(f"[HDC] 'alien_technology' (never seen) similarity: {hdc.query_similarity('alien_technology'):.3f}")
