import json
from typing import Dict, Any

from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType

TAG = __name__


class TtsStatusTextMessageHandler(TextMessageHandler):
    """TTS状态查询消息处理器"""

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        """处理TTS状态查询消息"""
        try:
            # 获取TTS状态信息
            tts_status = conn.get_tts_status()
            
            # 发送状态响应
            response = {
                "type": "tts_status",
                "status": "success",
                "data": tts_status
            }
            
            await conn.websocket.send(json.dumps(response, ensure_ascii=False))
            conn.logger.bind(tag=TAG).info(f"发送TTS状态响应: {tts_status}")
            
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"处理TTS状态查询失败: {e}")
            
            # 发送错误响应
            error_response = {
                "type": "tts_status",
                "status": "error",
                "message": str(e)
            }
            
            await conn.websocket.send(json.dumps(error_response, ensure_ascii=False))

    @property
    def message_type(self) -> TextMessageType:
        """返回处理的消息类型"""
        return TextMessageType.TTS_STATUS
