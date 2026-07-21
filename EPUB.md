# Build the EPUB editions

The repository can build EPUB 3 editions for Chinese, English, Tamil, and Vietnamese from the same Markdown sources used by the PDF editions.

Install [Pandoc](https://pandoc.org/), Poppler (`pdftoppm`), and optionally [EPUBCheck](https://www.w3.org/publishing/epubcheck/). The builder uses each PDF's first page as the corresponding EPUB cover. When EPUBCheck is available, the builder validates every generated book.

Build every language from the repository root:

```bash
./build_epub.sh
```

Build one language by passing its language code:

```bash
./build_epub.sh zh-CN
./build_epub.sh en
./build_epub.sh ta
./build_epub.sh vi
```

The builder writes each `.epub` beside its language's PDF. Generated EPUB files are ignored by Git.
