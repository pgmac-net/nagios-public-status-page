# Logo and Favicon Files

This directory contains the logo and favicon files for the status page.

## Files

- `logo.svg` - Main logo (48x48) used in the header
- `favicon.svg` - Favicon optimized for small sizes (32x32)
- `favicon-16x16.png` - PNG favicon for 16x16 (needs to be generated)
- `favicon-32x32.png` - PNG favicon for 32x32 (needs to be generated)

## Generating PNG Favicons

Modern browsers support SVG favicons, but for broader compatibility, you should generate PNG versions.

### Option 1: Using ImageMagick (recommended)

```bash
cd static/img

# Generate 32x32 PNG
convert -background none favicon.svg -resize 32x32 favicon-32x32.png

# Generate 16x16 PNG
convert -background none favicon.svg -resize 16x16 favicon-16x16.png
```

### Option 2: Using Inkscape

```bash
cd static/img

# Generate 32x32 PNG
inkscape -w 32 -h 32 favicon.svg -o favicon-32x32.png

# Generate 16x16 PNG
inkscape -w 16 -h 16 favicon.svg -o favicon-16x16.png
```

### Option 3: Using rsvg-convert

```bash
cd static/img

# Generate 32x32 PNG
rsvg-convert -w 32 -h 32 favicon.svg -o favicon-32x32.png

# Generate 16x16 PNG
rsvg-convert -w 16 -h 16 favicon.svg -o favicon-16x16.png
```

### Option 4: Online Tools

If you don't have these tools installed, you can use online converters:
- https://cloudconvert.com/svg-to-png
- https://convertio.co/svg-png/
- https://www.aconvert.com/image/svg-to-png/

Upload `favicon.svg` and convert to:
1. 32x32 PNG (save as `favicon-32x32.png`)
2. 16x16 PNG (save as `favicon-16x16.png`)

## Installing ImageMagick

### macOS
```bash
brew install imagemagick
```

### Ubuntu/Debian
```bash
sudo apt-get install imagemagick
```

### Docker (if running in container)
```bash
# Add to Dockerfile
RUN apk add --no-cache imagemagick
# or for debian-based
RUN apt-get update && apt-get install -y imagemagick
```

## Note

The SVG favicon (`favicon.svg`) will work in most modern browsers. The PNG versions are fallbacks for older browsers and certain contexts (like browser tabs in some browsers).
