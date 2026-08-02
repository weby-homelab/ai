#!/usr/bin/env python3
import os
import re
import sys


def extract_links(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match [text](link) and exclude URLs starting with http/https/mailto
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    links = re.findall(pattern, content)

    relative_links = []
    for text, link in links:
        # Strip anchor links like #anchor
        clean_link = link.split("#")[0]
        if not clean_link:
            continue
        if not (clean_link.startswith(("http://", "https://", "mailto:"))):
            relative_links.append((text, clean_link))

    return relative_links


def verify_file_links(file_path):
    print(f"Checking links in: {file_path}")
    base_dir = os.path.dirname(file_path)
    links = extract_links(file_path)

    broken_links = 0
    for text, link in links:
        # Resolve relative link from current file path
        # Replace URL-encoded characters like %20 or &nbsp; if they are in links
        decoded_link = link.replace("%20", " ")
        target_path = os.path.abspath(os.path.join(base_dir, decoded_link))

        if not os.path.exists(target_path):
            print(f"  ❌ Broken link: '{text}' -> '{link}' (Resolved to: {target_path})")
            broken_links += 1
        else:
            print(f"  ✅ OK: '{text}' -> '{link}'")

    return broken_links


def main():
    files_to_check = [
        "README.md",
        "README_ENG.md",
        "docs/security/model-vetting.md",
        "docs/templates.md",
        "docs/templates_ENG.md",
        "docs/setup/reference-architectures.md",
        "docs/setup/ai-ops.md",
        "docs/security/threat-modeling.md",
        "docs/setup/blackout-guide.md",
        "benchmarks/hardware_efficiency.md",
        "configs/production-agent-stack/README.md",
    ]

    total_broken = 0
    for rel_path in files_to_check:
        abs_path = os.path.abspath(rel_path)
        if not os.path.exists(abs_path):
            print(f"File to check not found: {abs_path}")
            sys.exit(1)
        total_broken += verify_file_links(abs_path)

    if total_broken > 0:
        print(f"\nVerification failed: {total_broken} broken links found.")
        sys.exit(1)
    else:
        print("\nAll relative links are verified successfully! 🎉")
        sys.exit(0)


if __name__ == "__main__":
    main()
