#enum.py

from enum import Enum


# Mineru API 响应码与任务状态映射
MINERU_API_CODE_SUCCESS = 0
MINERU_TASK_STATE_MAP = {
	"done": "任务处理状态，完成",
	"pending": "任务处理状态，排队中",
	"running": "任务处理状态，正在解析",
	"failed": "任务处理状态，解析失败",
	"waiting-file": "任务处理状态，等待文件上传",
	"converting": "任务处理状态，格式转换中",
}

# Mineru API 常见错误码说明与解决建议
MINERU_ERROR_DETAIL_MAP = {
	"A0202": ("Token 错误", "检查 Token 是否正确，请检查是否有Bearer前缀 或者更换新 Token"),
	"A0211": ("Token 过期", "更换新 Token"),
	"-500": ("传参错误", "请确保参数类型及Content-Type正确"),
	"-10001": ("服务异常", "请稍后再试"),
	"-10002": ("请求参数错误", "检查请求参数格式"),
	"-60001": ("生成上传 URL 失败，请稍后再试", "请稍后再试"),
	"-60002": ("获取匹配的文件格式失败", "检测文件类型失败，请求的文件名及链接中带有正确的后缀名，且文件为 pdf,doc,docx,ppt,pptx,png,jp(e)g 中的一种"),
	"-60003": ("文件读取失败", "请检查文件是否损坏并重新上传"),
	"-60004": ("空文件", "请上传有效文件"),
	"-60005": ("文件大小超出限制", "检查文件大小，最大支持 200MB"),
	"-60006": ("文件页数超过限制", "请拆分文件后重试"),
	"-60007": ("模型服务暂时不可用", "请稍后重试或联系技术支持"),
	"-60008": ("文件读取超时", "检查 URL 可访问"),
	"-60009": ("任务提交队列已满", "请稍后再试"),
	"-60010": ("解析失败", "请稍后再试"),
	"-60011": ("获取有效文件失败", "请确保文件已上传"),
	"-60012": ("找不到任务", "请确保task_id有效且未删除"),
	"-60013": ("没有权限访问该任务", "只能访问自己提交的任务"),
	"-60014": ("删除运行中的任务", "运行中的任务暂不支持删除"),
	"-60015": ("文件转换失败", "可以手动转为pdf再上传"),
	"-60016": ("文件转换失败", "文件转换为指定格式失败，可以尝试其他格式导出或重试"),
	"-60017": ("重试次数达到上线", "等后续模型升级后重试"),
	"-60018": ("每日解析任务数量已达上限", "明日再来"),
	"-60019": ("html文件解析额度不足", "明日再来"),
	"-60020": ("文件拆分失败", "请稍后重试"),
	"-60021": ("读取文件页数失败", "请稍后重试"),
	"-60022": ("网页读取失败", "可能因网络问题或者限频导致读取失败，请稍后重试"),
}
class mineru_response_code(Enum):
	SUCCESS = "0"
	TOKEN_INVALID = "A0202"
	TOKEN_EXPIRED = "A0211"
	PARAM_ERROR = "-500"
	SERVICE_ERROR = "-10001"
	REQUEST_PARAM_ERROR = "-10002"
	UPLOAD_URL_FAILED = "-60001"
	FILE_FORMAT_NOT_MATCH = "-60002"
	FILE_READ_FAILED = "-60003"
	EMPTY_FILE = "-60004"
	FILE_TOO_LARGE = "-60005"
	FILE_PAGES_EXCEED = "-60006"
	MODEL_SERVICE_UNAVAILABLE = "-60007"
	FILE_READ_TIMEOUT = "-60008"
	QUEUE_FULL = "-60009"
	PARSE_FAILED = "-60010"
	VALID_FILE_NOT_FOUND = "-60011"
	TASK_NOT_FOUND = "-60012"
	TASK_NO_PERMISSION = "-60013"
	DELETE_RUNNING_TASK = "-60014"
	FILE_CONVERT_FAILED_PDF = "-60015"
	FILE_CONVERT_FAILED_FORMAT = "-60016"
	RETRY_LIMIT_REACHED = "-60017"
	DAILY_TASK_LIMIT_REACHED = "-60018"
	HTML_QUOTA_INSUFFICIENT = "-60019"
	FILE_SPLIT_FAILED = "-60020"
	FILE_PAGE_COUNT_FAILED = "-60021"
	WEB_READ_FAILED = "-60022"


