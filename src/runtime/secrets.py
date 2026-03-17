import os
import pathlib
import re
import ast

class ConfigNode:
    def __init__(self, data=None):
        self._data = data or {}

    def __getattr__(self, name):
        if name in self._data:
            val = self._data[name]
            if isinstance(val, dict):
                return ConfigNode(val)
            return val
        return os.environ.get(name, "")

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __str__(self):
        return str(self._data)

class NexaSecrets:
    """
    负责管理 Nexa 的秘钥 (.nxs 文件) 和环境变量
    """
    def __init__(self):
        self._configs = {}
        self._load_secrets()
        
    def _parse_nxs(self, content):
        # Strip full line comments
        content = re.sub(r'^\s*//.*', '', content, flags=re.MULTILINE)
        
        blocks = {}
        
        # A simple state machine to extract config blocks with balanced braces
        idx = 0
        while idx < len(content):
            # find next config
            match = re.search(r'config\s+([a-zA-Z0-9_]+)\s*\{', content[idx:])
            if not match:
                break
                
            config_name = match.group(1)
            start_brace = idx + match.end() - 1
            
            # find matching end brace
            brace_count = 0
            end_brace = -1
            for i in range(start_brace, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_brace = i
                        break
                        
            if end_brace == -1:
                break
                
            config_body = content[start_brace+1:end_brace]
            idx = end_brace + 1
            
            lines = config_body.split('\n')
            parsed_lines = []
            for line in lines:
                line = line.rstrip()
                if not line:
                    continue
                # Replace key = ... with "key": ...
                line = re.sub(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]+)\s*=\s*(.*)', r'\1"\2": \3', line)
                if not line.endswith('{') and not line.endswith(','):
                    line += ','
                parsed_lines.append(line)
            
            code_str = "tmp_dict = {\n" + "\n".join(parsed_lines) + "\n}"
            
            try:
                local_env = {}
                exec(code_str, {}, local_env)
                blocks[config_name] = ConfigNode(local_env.get("tmp_dict", {}))
            except Exception as e:
                print(f"[Secrets Parser Error] snippet failed: {e}")
                print(f"Code string was:\n{code_str}")
                
        return blocks

    def _load_secrets(self):
        # 寻找当前执行目录下的 secrets.nxs
        secrets_file = pathlib.Path.cwd() / "secrets.nxs"
        if secrets_file.exists():
            with open(secrets_file, "r", encoding="utf-8") as f:
                content = f.read()
            self._configs = self._parse_nxs(content)

    def __getattr__(self, name):
        if name in self._configs:
            return self._configs[name]
        return ConfigNode()

    def get(self, key: str):
        # Fallback for old secret("KEY") calls
        return os.environ.get(key, "")

# 单例实例
nexa_secrets = NexaSecrets()
