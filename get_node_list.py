import logging
from typing import List

def process_providers(file_path: str, provider_type: str) -> None:
    """处理代理提供者文件"""
    # 假设这是处理逻辑
    pass

def merge_yamls(file_paths: List[str], output_file: str) -> None:
    """合并YAML文件"""
    # 假设这是合并逻辑
    pass

def main() -> None:
    """主函数，执行所有处理流程"""

    # 下载基础文件
    logging.info("Processing proxy providers...")
    process_providers("templates/proxy-providers.yaml", "proxy")
    logging.info("Processing proxy providers (baipiao)...")
    process_providers("templates/proxy-providers_baipiao.yaml", "proxy")
    logging.info("Processing rule providers...")
    process_providers("templates/rules_group.yaml", "rule")

    # 合并配置文件
    logging.info("Merging YAML files for clash_config_v3.yaml...")
    merge_yamls(
        ["head.yaml", "proxy-providers.yaml", "rules_group.yaml"],
        "clash_config_v3.yaml",
    )
    logging.info("Merging YAML files for config_mobile.yaml...")
    merge_yamls(
        [
            "head_mobile.yaml",
            "proxy-providers.yaml",
            "rules_group_mobile.yaml",
        ],
        "config_mobile.yaml",
    )
    logging.info("Merging YAML files for config_mobile_baipiao.yaml...")
    merge_yamls(
        ["head.yaml", "proxy-providers_baipiao.yaml", "rules_group.yaml"],
        "config_mobile_baipiao.yaml",
    )
    logging.info("Merging YAML files for config_magisk.yaml...")
    merge_yamls(
        ["proxy-providers.yaml", "rules_group.yaml"], "config_magisk.yaml"
    )