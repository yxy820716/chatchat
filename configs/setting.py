import yaml

def get_config(path):
    with open(path, "r", encoding="utf-8") as f:
        model_config = yaml.safe_load(f)
    return model_config


import yaml
from pathlib import Path
from typing import Dict, Any

def add_model_config(yaml_path: str, model_name: str, base_url: str, api_key: str) -> bool:
    """
    向YAML文件添加模型配置
    
    Args:
        yaml_path: YAML文件路径
        model_name: 模型名称
        base_url: API基础URL
        api_key: API密钥
    
    Returns:
        bool: 操作是否成功
    """
    try:
        # 读取现有的YAML文件
        config_path = Path(yaml_path)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file) or {}
        else:
            config = {}
        
        # 确保OPENAI_MODEL_NAME键存在
        if 'OPENAI_MODEL_NAME' not in config:
            config['OPENAI_MODEL_NAME'] = {}
        
        # 添加或更新模型配置
        config['OPENAI_MODEL_NAME'][model_name] = {
            'OPENAI_BASE_URL': base_url,
            'OPENAI_API_KEY': api_key
        }
        
        # 写回YAML文件
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        
        return True
        
    except Exception as e:
        print(f"添加模型配置失败: {e}")
        return False

def remove_model_config(yaml_path: str, model_name: str) -> bool:
    """
    从YAML文件删除模型配置
    
    Args:
        yaml_path: YAML文件路径
        model_name: 要删除的模型名称
    
    Returns:
        bool: 操作是否成功
    """
    try:
        # 读取现有的YAML文件
        config_path = Path(yaml_path)
        if not config_path.exists():
            print("YAML文件不存在")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file) or {}
        
        # 检查配置是否存在
        if ('OPENAI_MODEL_NAME' not in config or 
            model_name not in config['OPENAI_MODEL_NAME']):
            print(f"模型 '{model_name}' 不存在于配置中")
            return False
        
        # 删除模型配置
        del config['OPENAI_MODEL_NAME'][model_name]

        # 写回YAML文件
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        
        return True
        
    except Exception as e:
        print(f"删除模型配置失败: {e}")
        return False






def add_default_model(model_name,yaml_path) -> bool:
    """
    向YAML文件添加模型配置
    
    Args:
        yaml_path: YAML文件路径
        model_name: 模型名称
        base_url: API基础URL
        api_key: API密钥
    
    Returns:
        bool: 操作是否成功
    """
    try:
        # 读取现有的YAML文件
        config_path = Path(yaml_path)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file) or {}
        else:
            config = {}

        
        # 添加或更新模型配置
        config['DEFAULT_MODEL'] = model_name
        
        # 写回YAML文件
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        
        return True
        
    except Exception as e:
        print(f"添加模型配置失败: {e}")
        return False
    

def remove_default_model(model_name,yaml_path) -> bool:
    """
    从YAML文件删除模型配置
    
    Args:
        yaml_path: YAML文件路径
        model_name: 要删除的模型名称
    
    Returns:
        bool: 操作是否成功
    """
    try:
        # 读取现有的YAML文件
        config_path = Path(yaml_path)
        if not config_path.exists():
            print("YAML文件不存在")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file) or {}
        
        # 删除模型配置
        del config['DEFAULT_MODEL'][model_name]
        
        # 写回YAML文件
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        
        return True
        
    except Exception as e:
        print(f"删除模型配置失败: {e}")
        return False
# 使用示例
if __name__ == "__main__":

    
    # 添加另一个模型
    # add_model_config(
    #     yaml_path="/root/Yy/chatchat/configs/Model_Config.yaml",
    #     model_name="gpt-4",
    #     base_url="https://api.openai.com/v1",
    #     api_key="sk-your-openai-api-key"
    # )
    
    # 删除模型配置
    # remove_model_config("/root/Yy/chatchat/configs/Model_Config.yaml", "gpt-4")

    add_default_model("cscs")