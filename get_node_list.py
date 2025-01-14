"""Clash 配置文件處理工具

此腳本用於處理 Clash 配置文件，包括：
1. 下載 proxy 和 rule providers
2. 合併多個 YAML 配置文件
3. 自動創建所需目錄結構
"""

from typing import Dict, List, Optional, Set, Union
import yaml
import requests
import chardet
import os
import logging


# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def create_parent_directory(file_path: str) -> None:
    """
        創建文件的父目錄
    
    Args:
        file_path (str): 文件路徑
    """
    parent_dir = os.path.dirname(file_path)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)


def detect_encoding(file: str) -> str:
    """
        檢測文件的編碼
    
    Args:
        file (str): 文件路徑
        
    Returns:
        str: 檢測到的文件編碼
    """
    with open(file, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']


def parse_yaml(file_path: str) -> Optional[Dict]:
    """
        解析 YAML 文件
    
    Args:
        file_path (str): YAML 文件路徑
        
    Returns:
        Optional[Dict]: 解析後的字典數據，如果解析失敗則返回 None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        return data
    except Exception as e:
        logging.error(f"Error parsing YAML file {file_path}: {e}")
        return None


def merge_yamls(files: List[str], output_file: str) -> None:
    """
        合併多個 YAML 文件
    
    Args:
        files (List[str]): 要合併的文件列表
        output_file (str): 輸出文件路徑
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as output:
            for file_name in files:
                file_path = os.path.join('templates', file_name)
                with open(file_path, 'r', encoding='utf-8') as input_file:
                    output.write(input_file.read())
        logging.info(f"Successfully merged files into {output_file}")
    except Exception as e:
        logging.error(f"Error merging YAML files: {e}")


def download_file(url: str, path: str) -> None:
    """
        下載文件
    
    Args:
        url (str): 文件下載 URL
        path (str): 本地保存路徑
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        create_parent_directory(path)
        with open(path, 'wb') as f:
            f.write(response.content)
        logging.info(f"Successfully downloaded file from {url} to {path}")
    except Exception as e:
        logging.error(f"Error downloading file from {url}: {e}")


def process_providers(file_path: str, provider_type: str) -> None:
    """
        處理 proxy 或 rule providers
    
    Args:
        file_path (str): 配置文件路徑
        provider_type (str): provider 類型 ('proxy' 或 'rule')
    """
    data = parse_yaml(file_path)
    if not data:
        return

    downloaded_files: Set[str] = set()

    for provider, info in data[f'{provider_type}-providers'].items():
        url = info['url']
        path = info['path']
        logging.info(f"{provider_type.capitalize()} Provider: {provider}")
        logging.info(f"URL: {url}")
        logging.info(f"Path: {path}")

        if url not in downloaded_files:
            download_file(url, path)
            downloaded_files.add(url)
        logging.info("")


def main() -> None:
    """主函數，執行所有處理流程"""
    
    # 下載基礎文件
    process_providers('templates/proxy-providers.yaml', 'proxy')
    process_providers('templates/proxy-providers_baipiao.yaml', 'proxy')
    process_providers('templates/rules_group.yaml', 'rule')

    # 合併配置文件
    merge_yamls(['head.yaml', 'proxy-providers.yaml', 'rules_group.yaml'], 'clash_config_v3.yaml')
    merge_yamls(['head_mobile.yaml', 'proxy-providers.yaml', 'rules_group_mobile.yaml'], 'config_mobile.yaml')
    merge_yamls(['head.yaml', 'proxy-providers_baipiao.yaml', 'rules_group.yaml'], 'config_mobile_baipiao.yaml')
    merge_yamls(['proxy-providers.yaml', 'rules_group.yaml'], 'config_magisk.yaml')


if __name__ == '__main__':
    main()