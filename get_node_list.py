import yaml
import requests
import chardet
import os


def detect_encoding(file):
    with open(file, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']


def parse_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
    return data


def merge_yamls(files, output_file):
    directory = 'templates'

    with open(output_file, 'w', encoding='utf-8') as output:
        for file_name in files:
            file_path = os.path.join(directory, file_name)
            with open(file_path, 'r', encoding='utf-8') as input_file:
                output.write(input_file.read())


def download_file(url, path):
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(path, 'wb') as f:
            f.write(response.content)
    except Exception as e:
        print(f"Error downloading file from {url}: {e}")


def get_node_list(file_path):
    data = parse_yaml(file_path)
    downloaded_files = set()

    for provider, info in data['proxy-providers'].items():
        url = info['url']
        path = info['path']
        print(f"Proxy Provider: {provider}")
        print(f"URL: {url}")
        print(f"Path: {path}")
        if url not in downloaded_files:
            download_file(url, path)
            downloaded_files.add(url)
        print()


def get_rules(file_path):
    data = parse_yaml(file_path)
    downloaded_files = set()

    for provider, info in data['rule-providers'].items():
        url = info['url']
        path = info['path']
        print(f"Rule Provider: {provider}")
        print(f"URL: {url}")
        print(f"Path: {path}")
        if url not in downloaded_files:
            download_file(url, path)
            downloaded_files.add(url)
        print()


if __name__ == '__main__':
    # 下载基础文件
    # get_node_list('templates/proxy-providers.yaml')
    # get_node_list('templates/proxy-providers_baipiao.yaml')
    # get_rules('templates/rules_group.yaml')

    # clash_config_v3
    file_list = ['head.yaml', 'proxy-providers.yaml', 'rules_group.yaml']
    merge_yamls(file_list, 'clash_config_v3.yaml')

    # mobile
    file_list = ['head_mobile.yaml', 'proxy-providers.yaml', 'rules_group_mobile.yaml']
    merge_yamls(file_list, 'config_mobile.yaml')

    # mobile-baipiao
    file_list = ['head.yaml', 'proxy-providers_baipiao.yaml', 'rules_group.yaml']
    merge_yamls(file_list, 'config_mobile_baipiao.yaml')

    # magisk
    file_list = ['proxy-providers.yaml', 'rules_group.yaml']
    merge_yamls(file_list, 'config_magisk.yaml')

