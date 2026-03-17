import os
import pathlib

class NexaSecrets:
    """
    负责管理 Nexa 的秘钥 (.nxs 文件) 和环境变量
    """
    def __init__(self):
        self._secrets = {}
        self._load_secrets()
        
    def _load_secrets(self):
        # 寻找当前执行目录下的 secrets.nxs
        secrets_file = pathlib.Path.cwd() / "secrets.nxs"
        if secrets_file.exists():
            with open(secrets_file, "r", encoding="utf-8") as f:
                content = f.read()
            config_dict = {}
            try:
                exec(content, {}, config_dict)
                for k, v in config_dict.items():
                    if k.isupper() and not k.startswith("_"):
                        self._secrets[k] = v
            except Exception as e:
                print(f"[Secrets Parser Error] failed to parse secrets.nxs: {e}")

    def get(self, key: str):
        # 优先从 .nxs 中获取，后降级到环境变量
        return self._secrets.get(key, os.environ.get(key, ""))

# 单例实例
nexa_secrets = NexaSecrets()
