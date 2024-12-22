import requests
import tqdm
import os
import pathlib
import yaml
import threading
import time
import gc
import urllib3
import sys
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)
token = os.environ.get("TOKEN")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.47"
}
IGNORED_PACKAGE = ["xxx"] # 改用 HEAD 请求，不再需要忽略大文件
EXCLUDED_CODE = [429]

def command_generator( # 在 Action 中，已经设置好了 Komac，这里直接调用
    token: str, id: str, version: str, reason: str
) -> bool:
    return f"komac remove --identifier {id} --version {version} --reason '{reason}' --submit --token {token}"

def scan(_yaml: dict, token: str):
    global headers
    id = _yaml["PackageIdentifier"]
    version = _yaml["PackageVersion"]
    url_list: list[dict] = _yaml["Installers"]
    error: int = 0
    if any(each in id for each in IGNORED_PACKAGE):
        print(f"Skipping {id}(version {version})")
        gc.collect()
        return None

    try:
        for each in url_list:
            print(f"Starting check {id}(version {version})")

            # 先尝试 HEAD 请求
            try:
                response = requests.head(each["InstallerUrl"], headers=headers, verify=False, timeout=10, allow_redirects=False)
                code = response.status_code
                if code >= 400 and code not in EXCLUDED_CODE:
                    error += 1
                elif 300 <= code < 400: # 300 重定向使用 GET 请求
                    print(f"Received {code} status code for {each['InstallerUrl']}, following redirect with GET request")
                    response = requests.get(each["InstallerUrl"], headers=headers, verify=False, timeout=10, stream=True)
                    code = response.status_code
                    if code >= 400 and code not in EXCLUDED_CODE:
                        error += 1
            except requests.RequestException:
                # 如果 HEAD 请求失败，尝试 GET 请求
                print(f"HEAD request failed, retrying with GET for {each['InstallerUrl']}")
                try:
                    response = requests.get(each["InstallerUrl"], headers=headers, verify=False, timeout=10, stream=True)
                    code = response.status_code
                    if code >= 400 and code not in EXCLUDED_CODE:
                        error += 1
                except requests.RequestException:
                    print(f"GET request also failed for {each['InstallerUrl']}")
                    error += 1 # GET 请求失败也算作错误
        else:  # 如果前面的循环没有 break，就会执行这个 else - 也就是说，如果所有的 url 都返回了 400 以上的状态码
            if error == len(url_list):
                command = command_generator(
                    token,
                    id,
                    version,
                    f"[Automated] It returns code over 400 in all urls"
                )
                url = f"https://api.github.com/repos/microsoft/winget-pkgs/pulls"
                gh_headers = {
                    "Authorization": f"token {token}", # token在前面传入
                    "Accept": "application/vnd.github.v3+json"
                }
                params = {
                    "state": "open",
                    "base": "master" # 只检查对于主分支的PR
                }
                response = requests.get(url, headers=gh_headers, params=params)
                response.raise_for_status() # 如果请求失败，抛出异常
                pulls = response.json() # 获取 PR 列表
                for pr in pulls:
                    if (id in pr["title"]) and (version in pr["title"]): # 如果已经有标题带有该软件包的 id 和版本的就不再提交 PR
                        print(f"Found existing PR for {id} {version} - {pr['html_url']}")
                        break
                else: # 如果没有找到对应的 PR，就提交一个新的
                    threading.Thread(
                        target=os.system, kwargs=dict(command=command), daemon=False
                    ).start()
                print(
                    f"{id}(version {version}) checks fail(return bad code), running",
                    command,
                    "to remove it",
                )
            else:
                print(f"{id}(version {version}) checks successful")
    except BaseException as e:
        print(f"{id} checks bad: {e}") # 告诉我为什么炸了
    gc.collect()

def scanner(path: pathlib.Path, token: str):
    list_thread: list[threading.Thread] = []
    for each in os.listdir(path):
        _path = path / each
        if _path.is_dir():
            scanner(_path, token)
        elif _path.is_file():
            if ".installer.yaml" in _path.name:
                _yaml = _path # 修改此行以适配Linux路径
                with open(_yaml, "r", encoding="utf-8") as f:
                    yaml_ = yaml.load(f.read(), yaml.FullLoader)
                    list_thread.append(
                        threading.Thread(target=scan, args=(yaml_, token), daemon=True)
                    )
    for each in list_thread:
        each.start()
        for _ in tqdm.tqdm(range(5), desc="Waiting for finish"):
            # 丢弃未存取的变量 i
            if each.is_alive():
                time.sleep(1)
            else:
                break
        else:
            print("This scanning time is up, stop waiting......")

def main():
    if len(sys.argv) < 2:
        raise Exception("Please provide a subdirectory to scan under manifests.")
    subdirectory = sys.argv[1]

    # global search winget-pkgs folder
    origin: list[pathlib.Path] = []
    for each in pathlib.Path(__file__).parents:
        if len(origin) > 0:
            break
        origin = [
            each / i / "manifests" for i in os.listdir(each) if "winget-pkgs" in i
        ]
    if len(origin) == 0:
        raise Exception("Cannot find winget-pkgs folder")
    folder = origin[0] / subdirectory
    del origin
    gc.collect()
    print(f"We've found the folder in {folder}")

    # scan
    scanner(folder, token)

if __name__ == "__main__":
    runner = threading.Thread(target=main, daemon=True)
    runner.start()
    for each in range(1, 5 * 60 * 60 + 50 * 60):
        if not runner.is_alive():
            print("All scanning tasks have completed, exiting......")
            break
        time.sleep(1)
    else:
        print("Scanning time is up, safely exiting......")
