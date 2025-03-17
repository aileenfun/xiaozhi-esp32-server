import google.generativeai as genai
from core.utils.util import check_model_key
from core.providers.llm.base import LLMProviderBase
from config.logger import setup_logging
import requests
import json
TAG = __name__
logger = setup_logging()

class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        """初始化Gemini LLM Provider"""
        self.model_name = config.get("model_name", "gemini-1.5-pro")
        self.api_key = config.get("api_key")
        self.http_proxy=config.get("http_proxy")
        self.https_proxy = config.get("https_proxy")
        have_key = check_model_key("LLM", self.api_key)

        if not have_key:
            return

        try:
            # 初始化Gemini客户端
            # 配置代理（如果提供了代理配置）
            self.proxies=None
            if self.http_proxy is not "" or self.https_proxy is not "":

                self.proxies = {
                    "http": self.http_proxy,
                    "https": self.https_proxy,
                }
                logger.bind(tag=TAG).info(f"Gemini set proxys:{self.proxies}")
                # 使用猴子补丁修改 google-generativeai 库的请求会话

                # 使用 session 对象配置 genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)

            # 设置生成参数
            self.generation_config = {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            self.chat = None
        except Exception as e:
            logger.bind(tag=TAG).error(f"Gemini初始化失败: {e}")
            self.model = None

    def response(self, session_id, dialogue):
        """生成Gemini对话响应"""
        if not self.model:
            yield "【Gemini服务未正确初始化】"
            return

        try:
            # 处理对话历史
            chat_history = []
            for msg in dialogue[:-1]:  # 历史对话
                role = "model" if msg["role"] == "assistant" else "user"
                content = msg["content"].strip()
                if content:
                    chat_history.append({
                        "role": role,
                        "parts": [{"text":content}]

                    })

            # 获取当前消息
            current_msg = dialogue[-1]["content"]

            # 构建请求体
            request_body = {
                "contents": chat_history + [{"role": "user", "parts": [{"text":current_msg}]}],
                "generationConfig": self.generation_config
            }

            # 构建请求URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

            # 构建请求头
            headers = {
                "Content-Type": "application/json",
            }

            # 发送POST请求,经测试手动 request 无法使用 stream 模式，但是文本消息其实也很快，stream 与否也无所谓
            if self.proxies:
                response = requests.post(url, headers=headers, json=request_body, stream=False, proxies=self.proxies)
            else:
                response = requests.post(url, headers=headers, json=request_body, stream=False)
            response.raise_for_status()
            try:
                data = response.json()  # 直接解析JSON
                if 'candidates' in data and data['candidates']:
                    yield data['candidates'][0]['content']['parts'][0]['text']
                else:
                    yield "未找到候选回复。"
            except json.JSONDecodeError as e:
                yield f"JSON解码错误：{e}"
            except Exception as e:
                yield f"发生错误：{e}"


        except requests.exceptions.RequestException as e:
            yield f"请求失败：{e}"
        except json.JSONDecodeError as e:
            yield f"JSON解码错误：{e}"
        except Exception as e:
            yield f"发生错误：{e}"
