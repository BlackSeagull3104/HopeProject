"""Offline CPU inference worker. JSON-lines on private pipes; no network API."""
import json
from pathlib import Path
import sys


class Encoder:
    def __init__(self, directory):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        from .semantic_model import verify
        verify(directory)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(Path(directory) / 'model.onnx'),
            sess_options=options, providers=['CPUExecutionProvider'])
        self.tokenizer = Tokenizer.from_file(str(Path(directory) / 'tokenizer.json'))
        self.tokenizer.no_truncation()

    def chunks(self, text):
        # Offsets preserve original Unicode text; overlap 48 tokens. Every chunk
        # is re-encoded with prefix and specials and checked against the model cap.
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        offsets = tokens.offsets
        if not offsets: return []
        output = []
        for start in range(0, len(offsets), 432):
            end = min(start + 480, len(offsets))
            part = text[offsets[start][0]:offsets[end - 1][1]]
            output.append(part)
            if end == len(offsets): break
        return output

    def vector(self, text, kind):
        import numpy as np
        tokens = self.tokenizer.encode(f'{kind}: {text}')
        if len(tokens.ids) > 512: raise ValueError('Token limit')
        inputs = {name: np.array([values], dtype=np.int64) for name, values in (
            ('input_ids', tokens.ids), ('attention_mask', tokens.attention_mask),
            ('token_type_ids', tokens.type_ids))}
        output = self.session.run(None, inputs)[0]
        mask = inputs['attention_mask'][..., None]
        vector = (output * mask).sum(axis=1) / mask.sum(axis=1)
        vector = (vector / (np.linalg.norm(vector, axis=1, keepdims=True) + 1e-12)).astype(np.float32)[0]
        if vector.shape != (384,) or not np.isfinite(vector).all(): raise ValueError('Vector')
        return vector.tolist()

    def request(self, text, kind):
        if kind == 'query':
            parts = self.chunks(text)
            return [{'text': parts[0], 'vector': self.vector(parts[0], kind)}] if parts else []
        return [{'text': part, 'vector': self.vector(part, 'passage')} for part in self.chunks(text)]


def main():
    encoder = None
    for line in sys.stdin:
        try:
            body = json.loads(line)
            if encoder is None:
                encoder = Encoder(Path(body['model']))
                result = {'ready': True}
            else:
                result = encoder.request(body['text'], body['kind'])
            print(json.dumps(result, ensure_ascii=True), flush=True)
        except Exception:
            print('{"error":"Local semantic runtime unavailable"}', flush=True)
            return


if __name__ == '__main__':
    main()
