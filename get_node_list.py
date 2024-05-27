import yaml
import requests
import chardet


def detect_encoding(file):
    with open(file, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']


def parse_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
    return data


def merge_yamls(files, output_file):
    data = {}

    with open(output_file, 'w', encoding='utf-8') as output:
        # 遍歷每個 SQL 文件並將內容寫入輸出文件
        for file_name in files:
            # file_path = os.path.join(directory, file_name)
            with open(file_name, 'r', encoding='utf-8') as input_file:
                output.write(input_file.read())


def download_file(url, path):
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(path, 'wb') as f:
            f.write(response.content)
    except Exception as e:
        print(f"Error downloading file from {url}: {e}")


def main():
    file_path = 'clash_config_v3.yaml'
    data = parse_yaml(file_path)

    downloaded_files = set()

    for provider, info in data['proxy-providers'].items():
        url = info['url']
        path = info['path']
        print(f"Proxy Provider: {provider}")
        print(f"URL: {url}")
        print(f"Path: {path}")
        print()
        if url not in downloaded_files:
            download_file(url, path)
            downloaded_files.add(url)

    for provider, info in data['rule-providers'].items():
        url = info['url']
        path = info['path']
        print(f"Rule Provider: {provider}")
        print(f"URL: {url}")
        print(f"Path: {path}")
        print()
        if url not in downloaded_files:
            download_file(url, path)
            downloaded_files.add(url)


if __name__ == '__main__':
    # main()
    file_list = ['templates/head.yaml', 'templates/proxy-providers.yaml', 'templates/rules_group.yaml']
    merge_yamls(file_list, 'out.yaml')
