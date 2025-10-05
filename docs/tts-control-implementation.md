# TTS开关控制功能实现总结

## 📋 项目概述

本文档记录了在xiaozhi-server项目中实现TTS（Text-to-Speech）开关控制功能的完整过程，包括全局控制和单设备控制的实现。

## 🎯 需求背景

### 初始需求
- 实现全局TTS开关控制，允许在ASR+LLM处理后选择是否进行TTS语音合成
- 支持纯文本响应模式，不生成语音文件

### 扩展需求
- 实现单设备TTS开关控制，允许每个智能体/设备独立配置TTS行为
- 支持三种模式：
  - 使用全局配置（null值）
  - 强制启用TTS（true值）
  - 强制禁用TTS（false值）

## 🏗️ 系统架构

### 核心组件
- **xiaozhi-server**: Python AI语音服务核心
- **manager-api**: Spring Boot后端管理服务
- **manager-web**: Vue.js前端管理界面

### 数据流向
```
用户配置 → manager-web → manager-api → 数据库
                ↓
设备连接 → xiaozhi-server → 读取配置 → 应用TTS控制
```

## 🔧 技术实现

### 1. 全局TTS控制

#### 配置文件修改
**文件**: `main/xiaozhi-server/config.yaml`
```yaml
# 是否启用TTS语音合成，false时只返回文本不生成语音
enable_tts: true
```

#### 核心逻辑修改
**文件**: `main/xiaozhi-server/core/connection.py`

**关键功能**:
- 初始化全局TTS配置
- 设备特定配置覆盖全局配置
- TTS关闭时的协议兼容处理

**核心代码**:
```python
# TTS开关控制 - 初始化为全局配置
self.enable_tts = self.config.get("enable_tts", True)

# 处理单设备TTS开关配置
if private_config.get("enable_tts", None) is not None:
    self.enable_tts = private_config["enable_tts"]
    self._device_tts_override = True
else:
    self._device_tts_override = False

def _send_text_response(self, text):
    """当TTS关闭时，发送模拟的TTS协议流程"""
    # 模拟TTS协议：start → sentence_start → sentence_end → stop
    # 确保客户端兼容性
```

### 2. 单设备TTS控制

#### 数据库设计
**文件**: `main/manager-api/src/main/resources/sql/add_enable_tts_column.sql`
```sql
ALTER TABLE ai_agent ADD COLUMN enable_tts BOOLEAN DEFAULT NULL 
COMMENT '是否启用TTS语音合成（true启用，false禁用，null使用全局配置）';
CREATE INDEX idx_ai_agent_enable_tts ON ai_agent(enable_tts);
```

#### 后端实体和DTO
**文件**: `main/manager-api/src/main/java/xiaozhi/modules/agent/entity/AgentEntity.java`
```java
@Schema(description = "是否启用TTS语音合成（true启用，false禁用，null使用全局配置）")
private Boolean enableTts;
```

**文件**: `main/manager-api/src/main/java/xiaozhi/modules/agent/dto/AgentUpdateDTO.java`
```java
@Schema(description = "是否启用TTS语音合成（true启用，false禁用，null使用全局配置）", example = "true", nullable = true)
private Boolean enableTts;
```

#### 服务层实现
**文件**: `main/manager-api/src/main/java/xiaozhi/modules/agent/service/impl/AgentServiceImpl.java`

**关键问题解决**: MyBatis-Plus的null值更新策略
```java
// 使用混合策略：先更新普通字段，再单独处理enableTts
// 1. 使用updateById更新非null字段（安全）
boolean updateResult1 = this.updateById(existingEntity);

// 2. 单独更新enableTts字段（允许null值）
UpdateWrapper<AgentEntity> ttsUpdateWrapper = new UpdateWrapper<>();
ttsUpdateWrapper.eq("id", existingEntity.getId())
        .set("enable_tts", existingEntity.getEnableTts());
boolean updateResult2 = this.update(null, ttsUpdateWrapper);
```

#### 配置服务
**文件**: `main/manager-api/src/main/java/xiaozhi/modules/config/service/impl/ConfigServiceImpl.java`
```java
// 添加TTS开关配置
if (agent.getEnableTts() != null) {
    result.put("enable_tts", agent.getEnableTts());
}
```

#### 前端界面
**文件**: `main/manager-web/src/views/roleConfig.vue`

**Element UI null值处理**:
```html
<el-radio-group v-model="form.enableTts">
  <el-radio :label="'global'">{{ $t('roleConfig.useGlobalConfig') }}</el-radio>
  <el-radio :label="true">{{ $t('roleConfig.enableTtsOn') }}</el-radio>
  <el-radio :label="false">{{ $t('roleConfig.enableTtsOff') }}</el-radio>
</el-radio-group>
```

**数据转换逻辑**:
```javascript
// 保存时：'global' → null
enableTts: this.form.enableTts === 'global' ? null : this.form.enableTts

// 加载时：null → 'global'
enableTts: data.data.enableTts !== undefined ? 
    (data.data.enableTts === null ? 'global' : data.data.enableTts) : 'global'
```

### 3. TTS状态查询功能

#### 消息处理器
**文件**: `main/xiaozhi-server/core/handle/textHandler/ttsStatusMessageHandler.py`
```python
class TtsStatusTextMessageHandler(TextMessageHandler):
    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        tts_status = conn.get_tts_status()
        response = {
            "type": "tts_status",
            "status": "success", 
            "data": tts_status
        }
        await conn.websocket.send(json.dumps(response, ensure_ascii=False))
```

#### 测试客户端
**文件**: `main/xiaozhi-server/test/test_page.html`
```javascript
function queryTtsStatus() {
    const message = JSON.stringify({
        type: 'tts_status'
    });
    websocket.send(message);
}
```

## 🐛 关键问题与解决方案

### 问题1: MyBatis-Plus null值更新策略
**现象**: 选择"使用全局配置"时，数据库中的`enable_tts`字段没有被设置为NULL

**原因**: MyBatis-Plus默认忽略null值字段的更新，这是为了防止意外清空数据库字段的安全机制

**解决方案**: 使用混合更新策略
```java
// 先更新普通字段（保持安全性）
this.updateById(existingEntity);
// 再单独更新TTS字段（允许null值）
UpdateWrapper<AgentEntity> wrapper = new UpdateWrapper<>();
wrapper.eq("id", existingEntity.getId()).set("enable_tts", existingEntity.getEnableTts());
this.update(null, wrapper);
```

### 问题2: Element UI radio组件null值处理
**现象**: Vue.js的`el-radio`组件无法直接绑定null值

**原因**: Element UI的radio组件需要明确的label值，null值会导致绑定失效

**解决方案**: 使用字符串标识符
```javascript
// 前端使用'global'表示null
// 后端接收时转换为null
enableTts: this.form.enableTts === 'global' ? null : this.form.enableTts
```

### 问题3: TTS协议兼容性
**现象**: 关闭TTS后，客户端仍然期待TTS协议消息

**原因**: 客户端硬编码了TTS协议流程：start → sentence_start → sentence_end → stop

**解决方案**: 模拟TTS协议
```python
def _send_text_response(self, text):
    # 发送模拟的TTS协议消息，保持客户端兼容性
    # 包含动态延迟，模拟真实TTS处理时间
```

## 📊 测试验证

### 功能测试
1. **全局TTS控制**
   - ✅ 配置`enable_tts: false`，设备返回纯文本
   - ✅ 配置`enable_tts: true`，设备正常TTS

2. **单设备TTS控制**
   - ✅ 选择"使用全局配置"，数据库存储NULL
   - ✅ 选择"启用TTS"，数据库存储true
   - ✅ 选择"禁用TTS"，数据库存储false

3. **协议兼容性**
   - ✅ TTS关闭时，客户端正常接收响应
   - ✅ 客户端状态查询功能正常

### 数据库验证
```sql
-- 检查enable_tts字段状态
SELECT id, agent_name, enable_tts FROM ai_agent WHERE agent_name = '测试智能体';

-- 预期结果：
-- NULL: 使用全局配置
-- 1: 启用TTS  
-- 0: 禁用TTS
```

## 🔍 技术要点总结

### MyBatis-Plus更新策略
- **默认行为**: `updateById()`只更新非null字段
- **设计原因**: 防止意外清空数据库字段，提高安全性
- **解决方案**: 使用`UpdateWrapper`明确指定需要更新null值的字段

### Vue.js + Element UI null值处理
- **问题**: Element UI组件无法直接绑定null值
- **解决方案**: 使用字符串标识符进行转换
- **最佳实践**: 在数据层进行转换，保持UI层的简洁性

### WebSocket协议兼容性
- **挑战**: 客户端硬编码了协议流程
- **解决**: 模拟协议消息，保持向后兼容
- **原则**: 最小化客户端改动，服务端承担兼容性责任

## 📁 涉及文件清单

### xiaozhi-server (Python)
- `config.yaml` - 全局TTS配置
- `core/connection.py` - 核心连接处理逻辑
- `core/handle/intentHandler.py` - 意图处理逻辑
- `core/handle/textHandler/ttsStatusMessageHandler.py` - TTS状态查询处理器
- `core/handle/textMessageType.py` - 消息类型定义
- `core/handle/textMessageHandlerRegistry.py` - 消息处理器注册
- `test/test_page.html` - 测试客户端

### manager-api (Java Spring Boot)
- `src/main/java/xiaozhi/modules/agent/entity/AgentEntity.java` - 智能体实体
- `src/main/java/xiaozhi/modules/agent/dto/AgentUpdateDTO.java` - 更新DTO
- `src/main/java/xiaozhi/modules/agent/dto/AgentDTO.java` - 查询DTO
- `src/main/java/xiaozhi/modules/agent/service/impl/AgentServiceImpl.java` - 服务实现
- `src/main/java/xiaozhi/modules/agent/controller/AgentController.java` - 控制器
- `src/main/java/xiaozhi/modules/config/service/impl/ConfigServiceImpl.java` - 配置服务
- `src/main/resources/mapper/agent/AgentDao.xml` - MyBatis映射
- `src/main/resources/sql/add_enable_tts_column.sql` - 数据库迁移脚本

### manager-web (Vue.js)
- `src/views/roleConfig.vue` - 角色配置界面
- `src/i18n/zh_CN.js` - 国际化文本

## 🚀 部署说明

### 数据库迁移
```bash
# 执行数据库迁移脚本
mysql -u username -p database_name < main/manager-api/src/main/resources/sql/add_enable_tts_column.sql
```

### 服务重启
```bash
# 重启manager-api服务
# 重启xiaozhi-server服务
```

### 验证部署
1. 登录manager-web控制台
2. 进入智能体管理页面
3. 检查是否显示TTS配置选项
4. 测试配置保存和加载功能

## 📝 后续优化建议

### 功能增强
1. **批量配置**: 支持批量设置多个智能体的TTS配置
2. **配置模板**: 提供预设的TTS配置模板
3. **使用统计**: 统计TTS使用情况，优化资源配置

### 性能优化
1. **配置缓存**: 缓存智能体配置，减少数据库查询
2. **异步处理**: TTS协议模拟的异步处理
3. **连接池**: 优化数据库连接池配置

### 监控告警
1. **配置变更日志**: 记录TTS配置的变更历史
2. **异常监控**: 监控TTS处理异常情况
3. **性能指标**: 监控TTS响应时间和成功率

---

**文档版本**: v1.0  
**创建时间**: 2025-01-05  
**最后更新**: 2025-01-05  
**维护者**: AI Assistant
