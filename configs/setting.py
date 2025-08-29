import yaml

def get_config(path):
    with open(path, "r", encoding="utf-8") as f:
        model_config = yaml.safe_load(f)
    return model_config
