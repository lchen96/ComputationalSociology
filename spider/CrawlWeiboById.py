from bs4 import BeautifulSoup  # 对html页面进行解析
import requests  # 模拟发出请求
import js2py  # 将js代码转换为python 获取js中的变量值
import pandas as pd  # 存储文件
import json
import time
import re
import os  # 存储文件路径修改

# 所需字段
keys = ['text', 'reposts_count', 'comments_count', 'attitudes_count']
user_keys = ['follow_count', 'followers_count', 'gender',
             'profile_image_url', 'statuses_count', 'profile_image_url',
             'verified', 'verified_reason', 'verified_type']


# 将cookie字符串转换为字典
def get_cookie(cookie_str):
    cookies = {}
    lines = cookie_str.split(';')
    for line in lines:
        key, value = line.strip().split('=', 1)
        cookies[key] = value
    return cookies


# 此cookie仅为示范，每次爬数据前需要自己获取
cookie_str = '_T_WM=78253097119; SSOLoginState=1581256258; ALF=1583848255; SUB=_2A25zRH4RDeRhGeFM7VEZ8inEzzWIHXVQxwJZrDV6PUNbktANLRDZkW1NQNcWFBO_z69_s2Vnmx7zr5xs9DLQ4_NA; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WF9qh7GI2JY-yiHRaH.XhII5JpX5KzhUgL.FoMESoeReoMRSh.2dJLoIEBLxKqL1KqLB-qLxKqL1KqL1hMLxKnLBoBLBK-LxKnL1K-LB.-t; SUHB=0d4-ABMO7eLYE9; MLOGIN=1; M_WEIBOCN_PARAMS=luicode%3D20000174'
cookie_mobile = get_cookie(cookie_str)

# 将微博时间转换为时间戳
month_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def convert_time(weibo_time):
    strip_time = weibo_time.split()
    formalize_time = "%s-%02d-%s %s" % (
        strip_time[-1], month_list.index(strip_time[1]) + 1, strip_time[2], strip_time[3])
    timeArray = time.strptime(formalize_time, "%Y-%m-%d %H:%M:%S")
    time_stamp = time.mktime(timeArray)
    return int(time_stamp)


## 获取某微博id的具体信息（包含具体的发布时间）
def weibo_detail(weibo_id):
    weibo_content = {}
    url = r'https://m.weibo.cn/detail/%s' % str(weibo_id)
    html = requests.get(url)
    soup = BeautifulSoup(html.text, 'html.parser')
    script = soup.find_all("script")[1].text  # 定位含有微博信息的 js script
    render_data = js2py.eval_js(script + '$render_data')  # 将 js 执行转换 最后加上 $render_data 来获取 render_data 变量
    status = render_data['status'].to_dict()
    url2 = r'https://m.weibo.cn/statuses/extend?id=%s' % str(weibo_id)
    html2 = requests.get(url2)
    popularity = html2.json()['data']
    status.update(popularity)  # 将获取到的转发、评论、点赞数更新到原字典中
    weibo_content['time'] = convert_time(status['created_at'])  # 微博发布时间戳
    weibo_content['uid'] = status['user']['id']  # 用户id
    if 'raw_text' in status.keys():
        weibo_content['text'] = status['raw_text']
    else:
        weibo_content['text'] = status['text']
    for key in keys:
        weibo_content[key] = status.get(key, None)  # 有的字段可能无，尽量用get方法
    for key in user_keys:
        weibo_content[key] = status['user'].get(key, None)
    return weibo_content


## 根据 user_id 爬取用户的地区和生日
def user_info(user_id, cookie_mobile):
    url = r'https://weibo.cn/%s/info' % str(user_id)
    html = requests.get(url, cookies=cookie_mobile)
    soup = BeautifulSoup(html.text, 'html.parser')
    tips = soup.find_all('div', 'tip')
    u_info = ''
    for tip in tips:
        if tip.text == '基本信息':  # 定位到基本信息的div
            u_info = tip.next_sibling  # 具体的信息在基本信息div的下一个div
            break
    if u_info:
        u_info = [item.split(':') for item in re.split(r'<.+?>', str(u_info)) if ":" in item]
        u_info = {item[0]: item[1] for item in u_info}
        return {'location': u_info.get('地区', None), 'birth': u_info.get('生日', None)}  # 有的字段可能无，尽量用get方法
    else:  # 有的人可能没有这部分信息
        return {'location': None, 'birth': None}


user_id = 1709951635
user_info(user_id, cookie_mobile)


## 根据原微博 id 爬取所有转发的微博 id 及其对应的父亲节点微博 id
# 对列表的数据进行处理，仅保留 id 和 pid
def info(data, weibo_id):
    data_temp = []
    for item in data:
        temp = {}
        temp['id'] = int(item['id'])
        temp['pid'] = item.get('pid', weibo_id)
        data_temp.append(temp)
    return data_temp


# 动态加载获取转发列表
def repost(weibo_id):
    t0 = time.time()
    repost_list = []
    page = 1
    while True:
        try:
            url = r'https://m.weibo.cn/api/statuses/repostTimeline?id=%s&page=%s' % (str(weibo_id), str(page))
            page += 1
            html = requests.get(url)
            data = html.json()['data']['data']
            repost_list.extend(info(data, weibo_id))
        except:
            break  # 超出页数 请求出错 中断程序
    repost_list.append({'id': weibo_id, 'pid': None})  # 加上原始微博id 其父亲节点视作None
    print('爬取微博 %s 实际共 %8d 条转发 耗时 %.1f s' % (str(weibo_id), len(repost_list) - 1, time.time() - t0))
    return repost_list[::-1]  # 按时间先后顺序排列


## 根据weibo_id 爬取相关转发数据
def propagate_info(weibo_id, cookie_mobile):
    t1 = time.time()
    repost_info = []
    repost_ids = repost(weibo_id)  # 获取转发微博id和pid
    for item in repost_ids:
        weibo_content = weibo_detail(item['id'])
        item.update(weibo_content)
        # 获取用户信息地区、生日信息（由于要传 cookie 进去，速度会变慢，且有封号风险，不需要可注释掉）
        user_content = user_info(weibo_content['uid'], cookie_mobile)  # 若不需要可注释掉
        item.update(user_content)  # 若不需要可注释掉
        repost_info.append(item)
    print('爬取数据 %s 理论共 %8d 条转发 耗时 %.1f s' % (str(weibo_id), repost_info[0]['reposts_count'], time.time() - t1))
    return repost_info


## 存储数据 可存为json或csv
def save_data(weibo_data, save_path='./', filetype='json'):
    weibo_id = weibo_data[0]['id']
    filename = str(weibo_id) + '.' + filetype
    filename = os.path.join(save_path, filename)  # save_path 可修改为存储数据的路径
    if filetype == 'json':  # 存储为 json 格式的数据
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(weibo_data, f, ensure_ascii=False, indent=2)
    if filetype == 'csv':  # 存储为 csv 格式的数据
        df = pd.DataFrame(weibo_data)
        df.to_csv(filename, encoding='utf_8_sig', index=None)


# weibo_id = 4466322349607968 # 转发100多条
weibo_id = 4470091276084439  # 转发6条
weibo_data = propagate_info(weibo_id, cookie_mobile)
save_data(weibo_data, save_path='./', filetype='json')
