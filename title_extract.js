// title_extract.js —— 从 DSH 会话日志 (session.jsonl.zstd) 提取首句用户消息作为标题
//
// 用法: node title_extract.js <session.jsonl.zstd 路径>
// 输出: 首条 user/message 事件的纯文本（已截断 ~60 字符），无则输出空行
//
// 用 Node 内置 zlib.zstdDecompress（Node >= 22.24 / 23.4），与 DSH 使用的
// node:zlib zstd 完全一致。日志为"多帧串联"结构，逐帧解码后拼接。
const zlib = require('node:zlib')
const fs = require('node:fs')

const ZSTD_MAGIC = 0xfd2fb528

// 扫描所有完整 zstd 帧的字节范围（参考 DSH scanZstdFrames）
function scanFrames(buf) {
  const frames = []
  let offset = 0
  while (offset < buf.length) {
    const start = offset
    if (buf.length - offset < 4) break
    if (buf.readUInt32LE(offset) !== ZSTD_MAGIC) break
    offset += 4
    if (offset >= buf.length) break
    const descriptor = buf.readUInt8(offset)
    offset += 1
    const contentSizeFlag = descriptor >>> 6
    const singleSegment = (descriptor & 0x20) !== 0
    const checksum = (descriptor & 0x04) !== 0
    const dictionaryFlag = descriptor & 0x03
    const dictBytes = dictionaryFlag === 3 ? 4 : dictionaryFlag
    const contentSizeBytes = contentSizeFlag === 0 ? (singleSegment ? 1 : 0) : 1 << contentSizeFlag
    const rest = (singleSegment ? 0 : 1) + dictBytes + contentSizeBytes
    if (buf.length - offset < rest) break
    offset += rest
    for (;;) {
      if (buf.length - offset < 3) return frames
      const bh = buf.readUIntLE(offset, 3)
      offset += 3
      const lastBlock = (bh & 1) !== 0
      const blockType = (bh >>> 1) & 3
      const blockSize = bh >>> 3
      if (blockType === 3) return frames
      const payload = blockType === 1 ? 1 : blockSize
      if (buf.length - offset < payload) return frames
      offset += payload
      if (lastBlock) break
    }
    if (checksum) { if (buf.length - offset < 4) break; offset += 4 }
    frames.push([start, offset])
  }
  return frames
}

// 从一段 JSONL 文本中提取首个 user 消息文本
function extractFirstUserText(text) {
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (!t) continue
    let obj
    try { obj = JSON.parse(t) } catch { continue }
    if (!obj || obj.type !== 'user/message') continue
    const data = obj.data || {}
    const content = data.content
    if (!Array.isArray(content)) continue
    for (const block of content) {
      if (block && block.type === 'text' && typeof block.text === 'string' && block.text.trim()) {
        return block.text.replace(/\s+/g, ' ').trim()
      }
    }
  }
  return ''
}

const file = process.argv[2]
if (!file) { console.log(''); process.exit(0) }

try {
  const raw = fs.readFileSync(file)
  const frames = scanFrames(raw)
  let text = ''
  // 逐帧解码；一旦找到标题就停止（大多数情况第一帧即有用户消息）
  for (const [s, e] of frames) {
    try {
      text += zlib.zstdDecompressSync(raw.slice(s, e)).toString('utf8')
    } catch { continue }
    const hit = extractFirstUserText(text)
    if (hit) { console.log(hit.slice(0, 80)); process.exit(0) }
    if (text.length > 5000000) break  // 安全上限，防止异常超大日志
  }
  console.log('')
} catch { console.log('') }
