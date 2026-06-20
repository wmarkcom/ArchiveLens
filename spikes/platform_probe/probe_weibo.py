from common import build_arg_parser, run_probe


if __name__ == "__main__":
    args = build_arg_parser("weibo").parse_args()
    output_path = run_probe(
        platform="weibo",
        profile_url=args.profile_url,
        scrolls=args.scrolls,
        wait_ms=args.wait_ms,
        max_json=args.max_json,
        headless=args.headless,
        download_images=args.download_images,
        detail_pages=args.detail_pages,
    )
    print(f"探测结果已保存：{output_path}")
