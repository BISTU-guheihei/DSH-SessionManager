// Dependency-free asar reader v2: robust header detection.
// Usage:
//   node asar-list.js <archive> list
//   node asar-list.js <archive> extract <outDir> [pattern]
//   node asar-list.js <archive> extract-files <outDir> path1 path2 ...
const fs = require('fs');
const path = require('path');

const MAX_HEADER = 64 * 1024 * 1024;

function readHeader(archivePath) {
  const fd = fs.openSync(archivePath, 'r');
  try {
    const head = Buffer.alloc(16);
    fs.readSync(fd, head, 0, 16, 0);
    // bytes 0..15: pickle framing; the JSON string starts at offset 16.
    // Determine JSON length by scanning for the balanced top-level '}'.
    const chunkSize = 1024 * 1024;
    let offset = 16;
    let jsonBuf = Buffer.alloc(0);
    let depth = 0;
    let inString = false;
    let escaped = false;
    let jsonLen = -1;
    while (offset < MAX_HEADER) {
      const chunk = Buffer.alloc(chunkSize);
      const n = fs.readSync(fd, chunk, 0, chunkSize, offset);
      if (n === 0) break;
      jsonBuf = Buffer.concat([jsonBuf, chunk.subarray(0, n)]);
      for (let i = 0; i < n; i++) {
        const c = jsonBuf[jsonBuf.length - n + i];
        if (inString) {
          if (escaped) escaped = false;
          else if (c === 0x5c) escaped = true; // backslash
          else if (c === 0x22) inString = false; // "
        } else {
          if (c === 0x22) inString = true;
          else if (c === 0x7b) depth++; // {
          else if (c === 0x7d) { depth--; if (depth === 0) { jsonLen = jsonBuf.length - n + i + 1; break; } } // }
        }
      }
      if (jsonLen >= 0) break;
      offset += n;
    }
    if (jsonLen < 0) throw new Error('could not find end of header JSON');
    const header = JSON.parse(jsonBuf.subarray(0, jsonLen).toString('utf8'));
    return { header, dataStart: 16 + jsonLen };
  } finally {
    fs.closeSync(fd);
  }
}

function walk(node, prefix, out) {
  if (!node.files) return;
  for (const [name, child] of Object.entries(node.files)) {
    const p = prefix ? prefix + '/' + name : name;
    if (child.files) walk(child, p, out);
    else out.push({ path: p, offset: child.offset, size: child.size, unpacked: !!child.unpacked });
  }
}

function main() {
  const args = process.argv.slice(2);
  const archive = args[0];
  const cmd = args[1];
  const { header, dataStart } = readHeader(archive);
  const files = [];
  walk(header, '', files);

  if (cmd === 'list') {
    for (const f of files) console.log(`${f.offset}\t${f.size}\t${f.unpacked ? 'U' : 'P'}\t${f.path}`);
    return;
  }
  if (cmd === 'extract') {
    const outDir = args[2];
    const pattern = args[3] || '';
    const re = pattern ? new RegExp(pattern) : null;
    const matches = files.filter((f) => !re || re.test(f.path));
    let count = 0;
    for (const f of matches) {
      const outPath = path.join(outDir, f.path);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      if (f.unpacked) {
        const src = path.join(path.dirname(archive), path.basename(archive) + '.unpacked', f.path);
        if (fs.existsSync(src)) fs.copyFileSync(src, outPath);
      } else {
        fs.writeFileSync(outPath, readSlice(archive, dataStart + Number(f.offset), f.size));
      }
      count++;
    }
    console.log(`extracted ${count} files`);
    return;
  }
  if (cmd === 'extract-files') {
    const outDir = args[2];
    for (const rel of args.slice(3)) {
      const f = files.find((x) => x.path === rel);
      if (!f) { console.log('NOT FOUND: ' + rel); continue; }
      const outPath = path.join(outDir, rel);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      if (f.unpacked) {
        const src = path.join(path.dirname(archive), path.basename(archive) + '.unpacked', rel);
        if (fs.existsSync(src)) fs.copyFileSync(src, outPath);
      } else {
        fs.writeFileSync(outPath, readSlice(archive, dataStart + Number(f.offset), f.size));
      }
      console.log('extracted ' + rel + ' (' + f.size + ' bytes)');
    }
    return;
  }
  console.log('unknown cmd');
}

function readSlice(archivePath, start, size) {
  const fd = fs.openSync(archivePath, 'r');
  const buf = Buffer.alloc(size);
  let read = 0;
  while (read < size) {
    const n = fs.readSync(fd, buf, read, size - read, start + read);
    if (n === 0) break;
    read += n;
  }
  fs.closeSync(fd);
  return buf;
}

main();
