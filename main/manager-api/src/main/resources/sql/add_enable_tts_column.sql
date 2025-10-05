-- 为ai_agent表添加enable_tts字段
-- 用于控制单个智能体的TTS语音合成开关
-- 字段说明：
-- true: 启用TTS
-- false: 禁用TTS  
-- null: 使用全局配置

ALTER TABLE ai_agent ADD COLUMN enable_tts BOOLEAN DEFAULT NULL COMMENT '是否启用TTS语音合成（true启用，false禁用，null使用全局配置）';

-- 创建索引以提高查询性能
CREATE INDEX idx_ai_agent_enable_tts ON ai_agent(enable_tts);

-- 更新现有记录的注释
ALTER TABLE ai_agent MODIFY COLUMN enable_tts BOOLEAN DEFAULT NULL COMMENT '是否启用TTS语音合成（true启用，false禁用，null使用全局配置）';
