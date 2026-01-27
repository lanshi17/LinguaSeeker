# 安装: pip install fasttext
import fasttext
import os
from pathlib import Path
import tempfile
# 加载预训练模型 (需下载 lid.176.ftz)
# 优先使用环境变量指定的模型路径，其次使用缓存目录
env_model_path = os.environ.get("FASTTEXT_MODEL_PATH")
if env_model_path:
    model_path = env_model_path
else:
    cache_dir = os.environ.get("FASTTEXT_CACHE_DIR")
    if not cache_dir:
        # 使用系统临时目录作为默认缓存目录
        cache_dir = os.path.join(tempfile.gettempdir(), "fasttext_models")
    os.makedirs(cache_dir, exist_ok=True)
    model_path = os.path.join(cache_dir, "lid.176.ftz")

if not os.path.exists(model_path):
    import urllib.request
    print(f"Downloading language detection model to {model_path}...")
    urllib.request.urlretrieve(
        'https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz',
        model_path
    )
model = fasttext.load_model(model_path)

def detect_language(text_snippet):
    # 提取文档前 1000 字符作为样本
    predictions = model.predict(text_snippet.replace("\n", " "), k=1)
    lang_id = predictions[0][0].split("__")[-1] # 输出如 __label__zh
    
    # 映射到 MinerU 支持的格式
    lang_map = {
        "zh": ["ch"],          # 中文
        "en": ["en"],          # 英文
        "ja": ["ja"],          # 日文
        "de": ["de"],          # 德文
        "fr": ["fr"],          # 法文
        "ru": ["ru"],          # 俄文
        #"el": ["el"],          # 希腊文
        #"th": ["th"],          # 泰文
        
    }
    return lang_map.get(lang_id, ["en"]) # 默认英文