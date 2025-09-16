const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const pngToIco = require('png-to-ico');

async function main() {
  const srcSvg = path.join(__dirname, '..', 'build', 'icon.svg');
  const outDir = path.join(__dirname, '..', 'build');
  const sizes = [16, 24, 32, 48, 64, 128, 256];
  const pngPaths = [];

  if (!fs.existsSync(srcSvg)) {
    console.error('Missing build/icon.svg');
    process.exit(1);
  }
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  for (const size of sizes) {
    const outPng = path.join(outDir, `icon-${size}.png`);
    await sharp(srcSvg, { density: 384 })
      .resize(size, size)
      .png({ compressionLevel: 9 })
      .toFile(outPng);
    pngPaths.push(outPng);
  }

  const icoBuf = await pngToIco(pngPaths.filter(p => /icon-(16|24|32|48|64|128|256)\.png$/.test(p)));
  const icoPath = path.join(outDir, 'icon.ico');
  fs.writeFileSync(icoPath, icoBuf);
  console.log('Generated', icoPath);
}

main().catch(err => { console.error(err); process.exit(1); });

