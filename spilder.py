import json
import os
import re
from hashlib import md5
from multiprocessing import Pool
from urllib.parse import urlencode

import pymongo
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

from config import *

# mongodb 数据库对象
# connext=False表示进程启动的时候才进行连接
client = pymongo.MongoClient(MONGO_URL,connect=False)
db = client[MONGO_DB]


def get_page_index(offset, keyword):
    data = {
        "aid": "24",
        "app_name": "web_search",
        "offset": offset,
        "format": "json",
        "keyword": keyword,
        "autoload": "true",
        "count": "20",
        "en_qc": "1",
        "cur_tab": "1",
        "from": "search_tab",
        # "pd": "synthesis",
        # "timestamp": "1581315480994"
    }
    headers = {
        # 这里小心cookie失效的问题
        'cookie': 'tt_webid=6791640396613223949; WEATHER_CITY=%E5%8C%97%E4%BA%AC; tt_webid=6791640396613223949; csrftoken=4a29b1b1d9ecf8b5168f1955d2110f16; s_v_web_id=k6g11cxe_fWBnSuA7_RBx3_4Mo4_9a9z_XNI0WS8B9Fja; ttcid=3fdf0861117e48ac8b18940a5704991216; tt_scid=8Z.7-06X5KIZrlZF0PA9kgiudolF2L5j9bu9g6Pdm.4zcvNjlzQ1enH8qMQkYW8w9feb; __tasessionId=ngww6x1t11581323903383',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36'}
    url = 'https://www.toutiao.com/api/search/content/?' + urlencode(data)
    response = requests.get(url, headers=headers)
    try:
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('Request failed!')
        return None


def parse_page_index(html):
    data = json.loads(html)
    # json.loads()方法会格式化结果,并生成一个字典类型
    # print(data)
    # print(type(data))
    try:
        if data and 'data' in data.keys():
            for item in data.get('data'):
                if item.get('has_gallery'):
                    yield item.get('article_url')
    except TypeError:
        pass

def get_page_detail(url):
    headers = {
        'cookie': 'tt_webid=6791640396613223949; WEATHER_CITY=%E5%8C%97%E4%BA%AC; tt_webid=6791640396613223949; csrftoken=4a29b1b1d9ecf8b5168f1955d2110f16; s_v_web_id=k6g11cxe_fWBnSuA7_RBx3_4Mo4_9a9z_XNI0WS8B9Fja; ttcid=3fdf0861117e48ac8b18940a5704991216; tt_scid=8Z.7-06X5KIZrlZF0PA9kgiudolF2L5j9bu9g6Pdm.4zcvNjlzQ1enH8qMQkYW8w9feb; __tasessionId=yix51k4j41581315307695',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36',
        # ':scheme': 'https',
        # 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        # 'accept-encoding': 'gzip, deflate, br',
        # 'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7'
    }
    try:
        # 他妈的被自己蠢哭...忘了写headers了,搞了一个多小时
        response = requests.get(url, headers=headers)
        # print(response.status_code)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print("请求详情页出错!")
        return None


def parse_page_details(html, url):
    soup = BeautifulSoup(html, 'xml')
    title = soup.select('title')[0].get_text()
    # print(title)
    img_pattern = re.compile('JSON.parse\("(.*?)"\),', re.S)
    result = re.search(img_pattern, html)
    if result:
        # 这里注意一下双斜杠的问题
        data = json.loads(eval(repr(result.group(1)).replace('\\\\', '\\')))
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images: download_image(image)
            return {
                'title': title,
                'url': url,
                'images': images
            }


def save_to_mongo(result):
    if db[MONGO_TABLE].insert_one(result):
        print('存储到MongoDB成功', result)
        return True
    return False


def download_image(url):
    print('正在下载', url)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            save_img(response.content)
        return None
    except RequestException:
        print('请求图片出错', url)
        return None


def save_img(content):
    file_path = '{0}/img_download/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()


def main(offset):
    html = get_page_index(offset, KEY_WORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        if html:
            result = parse_page_details(html, url)
            if result: save_to_mongo(result)


if __name__ == '__main__':
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main, groups)
