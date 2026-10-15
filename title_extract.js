// title_extract.js —— 从 DSH 会话日志 (session.v4.jsonl.zstd / session.jsonl.zstd)
// 提取会话标题。
//
// 用法: node title_extract.js <会话日志路径>
// 输出: 一行 JSON（供 session_core.py 解析）：
//   {
//     "title":           DSH 自产标题（source.kind=provider，LLM 精炼，最佳）,
//     "fallback_title":  DSH fallback 标题（通常等于首句原文）,
//     "first_user_text": 首条“真实用户”消息全文（未截断）,
//     "cwd":             会话的工作目录（取自 session 事件）,
//     "user_msg_count":  真实用户消息条数,
//     "frames":          扫描到的 zstd 帧数
//   }
//
// 关键修复：
//   1. DSH 新版日志里自带 session/title 事件，里面是 DSH 已经生成好的短标题；
//      优先用它，首句很长时也不会出现乱码/一长串字母。
//   2. 只认 source.kind === 'user' 的用户消息——DSH 会把 runtime-context /
//      skill-catalog 等系统注入内容也写成 user/message，直接取第一条会抓错。
//   3. 一次扫描全部帧并解析；早期版本“每解码一帧就把累计文本重新逐行 JSON.parse”
//      是 O(n²)，长会话会拖慢甚至超时，导致标题取不到而回退成会话 ID。
//   4. 打印完整文本，不再在 JS 侧按字节截断（截断容易切坏多字节字符，
//      显示层的截断由 session_core.py 用 UTF-8 安全方式完成）。
//
// 用 Node 内置 zlib.zstdDecompress（Node >= 22.24 / 23.4），与 DSH 使用的
// node:zlib zstd 完全一致。日志为“多帧串联”结构，逐帧解码后拼接。
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

// 从消息 content 数组里取出纯文本
function textOfContent(content) {
  if (!Array.isArray(content)) return ''
  const parts = []
  for (const block of content) {
    if (block && block.type === 'text' && typeof block.text === 'string' && block.text.trim()) {
      parts.push(block.text)
    }
  }
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

// 清掉控制字符与零宽字符（标题里出现会破坏界面显示）
function sanitize(text) {
  if (typeof text !== 'string') return ''
  return text
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001F\u007F-\u009F\u200B-\u200F\u2028\u2029\uFEFF]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const file = process.argv[2]
if (!file) {
  console.log(JSON.stringify({ title: '', fallback_title: '', first_user_text: '', cwd: '' }))
  process.exit(0)
}

const out = {
  title: '',
  fallback_title: '',
  first_user_text: '',
  cwd: '',
  user_msg_count: 0,
  frames: 0,
}

try {
  const raw = fs.readFileSync(file)
  const frames = scanFrames(raw)
  out.frames = frames.length

  for (const [s, e] of frames) {
    let chunk
    try {
      chunk = zlib.zstdDecompressSync(raw.slice(s, e)).toString('utf8')
    } catch {
      continue
    }
    for (const line of chunk.split('\n')) {
      const t = line.trim()
      if (!t) continue
      let obj
      try { obj = JSON.parse(t) } catch { continue }
      if (!obj || typeof obj !== 'object') continue

      if (obj.type === 'session') {
        if (!out.cwd && typeof obj.cwd === 'string') out.cwd = obj.cwd
      } else if (obj.type === 'session/title') {
        const d = obj.data || {}
        const title = sanitize(d.title)
        if (title) {
          const kind = (d.source || {}).kind
          if (kind === 'provider') {
            out.title = title            // LLM 精炼标题，最佳
          } else if (kind === 'fallback') {
            out.fallback_title = title   // 首句原文
          } else if (!out.title && !out.fallback_title) {
            out.fallback_title = title
          }
        }
      } else if (obj.type === 'user/message') {
        const d = obj.data || {}
        const kind = (d.source || {}).kind
        // 只认真实用户输入，跳过 runtime-context / skill-catalog 等注入消息
        if (kind && kind !== 'user') continue
        out.user_msg_count += 1
        if (!out.first_user_text) out.first_user_text = textOfContent(d.content)
      }
    }
  }
} catch {
  // 读取/解码失败：输出空结果，让调用方降级处理
}

console.log(JSON.stringify(out))
