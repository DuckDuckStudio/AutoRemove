import requests
import pathlib
from urllib3.exceptions import InsecureRequestWarning
import urllib3
import os, sys
urllib3.disable_warnings(InsecureRequestWarning)
import json
import bs4
import re

GH_TOKEN = sys.argv[1]

def report_existed(id: str, Version: str) -> None:
    print(f"{id}: {Version} has already existed, skip publishing")

def komac(path: str, debug: bool = False) -> pathlib.Path:
    Komac = pathlib.Path(path)/"komac.exe"
    if not debug:
        with open(Komac, "wb+") as f:
            file = requests.get("https://github.com/Exorcism0666/Komac/releases/download/nightly/KomacPortable-nightly-x64.exe", verify=False)
            f.write(file.content)
    return Komac

def command(komac: pathlib.Path, id: str, urls: str, version: str, token: str) -> str:
    Commands = "{} update --identifier {} --urls {} --version {} --submit --token {}".format(komac.__str__(), id, urls, version, token)
    return Commands

def clean_string(string: str, keywords: dict[str, str]) -> str:
    for k in keywords:
        string = string.replace(k, keywords[k])
    return string

def str_pop(string: str, index: int) -> str:
        i = list(string)
        i.pop(index)
        i = "".join(i)

        return i

def list_to_str(List: list) -> str:
    new = str(List)
    new = clean_string(new, {
         "[": "",
         "]": "",
         " ": "",
         "'": "",
         ",": " "
    })
    return new

def version_verify(version: str, id: str) -> bool:
    # if len([v for v in requests.get(f"https://winget.vercel.app/api/winget-pkg-versions?pkgid={id}").json()[id] if v == version]) > 0:
    #     return False
    # else:
    return True # always returns true due to that the api has stopped by unknown issue

def do_list(id: str, version: str, mode: str) -> bool | None:
    """
    Mode: write or verify
    """
    path = pathlib.Path(__file__).parents[0] / "config" / "list.json"
    with open(path, "r", encoding="utf-8") as f:
        try:
            JSON: dict[str, list[str]] = json.loads(f.read())
        except BaseException:
            JSON: dict[str, list[str]] = {}
        if id not in JSON:
            JSON[id] = []
        
        if mode == "write":
            if version not in JSON[id]:
                JSON[id].append(version)
            with open(path, "w+", encoding="utf-8") as w:
                w.write(json.dumps(JSON))
        elif mode == "verify":
            if version in JSON[id]:
                return True
            else:
                return False
        else:
            raise Exception
 
def main() -> list[tuple[str, tuple[str, str, str]]]:
    Commands:list[tuple[str, tuple[str, str, str]]] = []
    debug = bool([each for each in sys.argv if each == "debug"])
    Komac = komac(pathlib.Path(__file__).parents[0], debug)
    Headers = [{
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.67",
    }, {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.67",
        "Authorization": f"Bearer {GH_TOKEN}"
    }]

# Add GitHub.Atom_Pckgr to Update List
    id = "GitHub.Atom_Pckgr"
    JSON = requests.get("https://api.github.com/repos/atom/atom/releases/latest", verify=False, headers=Headers[1]).json()["assets"]
    Version = requests.get("https://api.github.com/repos/atom/atom/releases/latest", verify=False, headers=Headers[1]).json()["tag_name"]
    Urls = [each["browser_download_url"] for each in JSON if ("exe" in each["browser_download_url"]) and ("x64" in each["browser_download_url"])]
    if not version_verify(str_pop(Version, 0), id):
         report_existed(id, Version)
    elif do_list(id, Version, "verify"):
        report_existed(id, Version)
    else:
        Commands.append((command(Komac, id, list_to_str(Urls), str_pop(Version, 0), GH_TOKEN), (id, Version, "write")))
    del JSON, Urls, Version, id

# Add GitHub.GitLFS_Pckgr to Update List
    id = "GitHub.GitLFS_Pckgr"
    JSON = requests.get("https://api.github.com/repos/git-lfs/git-lfs/releases/latest", verify=False, headers=Headers[1]).json()["assets"]
    Version = requests.get("https://api.github.com/repos/git-lfs/git-lfs/releases/latest", verify=False, headers=Headers[1]).json()["tag_name"]
    Urls = [each["browser_download_url"] for each in JSON if each["browser_download_url"].endswith(".exe")]
    if not version_verify(str_pop(Version, 0), id):
         report_existed(id, Version)
    elif do_list(id, Version, "verify"):
        report_existed(id, Version)
    else:
        Commands.append((command(Komac, id, list_to_str(Urls), str_pop(Version, 0), GH_TOKEN), (id, Version, "write")))
    del JSON, Urls, Version, id

    # Updating
    if not debug:
        for each in Commands:
            if os.system(each[0]) == 0:
                do_list(*each[1])
    
    # Cleanup the merged branch
    os.system(f"{Komac} cleanup --only-merged --token {GH_TOKEN}")

    return Commands

if __name__ == "__main__":
    print([each[0] for each in main()])