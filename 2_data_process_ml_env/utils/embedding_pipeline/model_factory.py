
def get_embedding_model(model_name: str, **kwargs):
    if model_name == "ts2vec":
        from .ts2vec_model import TS2VecEmbeddingModel
        return TS2VecEmbeddingModel(**kwargs)
    elif model_name == "bert":
        from .bert_model import BertEmbeddingModel
        return BertEmbeddingModel(**kwargs)
    else:
        raise ValueError(f"Unknown model: {model_name}")
