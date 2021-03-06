#Author: 13yyz
#coding:'utf-8'

import time
import signal
import multiprocessing
import redis

from Sqliscan import std
from Sqliscan import sqlerrors
from Sqliscan import web
from url_spider import *
from Sqliscan import serverinfo

def init():
    """
    初始化进程信号处理
    :return: None
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN) #预设信号处理函数,当产生信号时，无视信号

def scan(urls):
    """
    多线程扫描url
    :param urls: url列表
    :return: 有漏洞的urls
    """
    vulnerables = [] #存储有漏洞的url
    results = {} #存储扫描结果

    childs = []  #存储子线程
    max_processes = 8
    pool = multiprocessing.Pool(max_processes, init)

    for url in urls:
        def callback(result, url=url):
            results[url] = result
        childs.append(pool.apply_async(__sqli,(url, ),callback=callback))

    try:
        while True:
            time.sleep(0.5)
            if all([child.ready() for child in childs]):
                break
    except Exception:
        # std.stderr("stopping sqli scanning process")
        pool.terminate()
        pool.join()
    else:
        pool.close()
        pool.join()

    for url, result in results.items():
        if result[0] == True:
            vulnerables.append((url, result[1]))
    return vulnerables

def __sqli(url):
    """
       检测SQL注入漏洞函数
       :param url: url
       :return:
    """
    # std.stdout("scanning {}".format(url),end="\n")
    domain = url.split("?")[0] #取域名
    queries = urlparse(url).query.split("&") #解析参数

    #url中没有参数
    if not any(queries):
        return False, None

    payloads = ("'", "')", "';", '"', '")', '";', '`', '`)', '`;', '\\', "%27", "%%2727", "%25%27", "%60", "%5C")
    for payload in payloads:
        website = domain + "?" + ("&".join([param + payload for param in queries]))
        source = web.gethtml(website)
        if source:
            vulnerable,db = sqlerrors.check(source)
            if vulnerable and db != None:
                # std.showsign("vulnerable")
                return True, db

    return False, None

def redis_connect(savepool):

    spider_redis = redis.Redis(connection_pool=savepool)
    return spider_redis

def is_vulnerable(urls):
    if not urls:
        # std.stdout("no vulnerables webistes")
        return True,None
    else:
        # std.stdout("scanning server information")
        vulnerableurls = [result[0] for result in urls]
        table_data = serverinfo.check(vulnerableurls)
        json_obj = std.dumpjson(table_data)
        for result, info in zip(urls, table_data):
            info.insert(1, result[1])
        std.fullprint(table_data)
        return True,json_obj


class SqliMain(object):

    def __init__(self,savepool):
        self.savepool = savepool
        self.sqli_redis = redis_connect(self.savepool)
        self.finished = False

    def run(self):
        self.action = self.sqli_redis.get('sqli_args')
        while True:
            finished = self.sqli_redis.get('spider_redis')
            if finished == 'True':
                print("good")
                break
            time.sleep(20)
        if self.action == 'run':
            urlset = self.sqli_redis.smembers("Spider_full_urls")
            vulnerables = scan(urlset)
            result = is_vulnerable(vulnerables)
            self.finished = result[0]
            self.redis_set(result[1])

    def redis_set(self, url):
        #store vulnerableurls
        try:
            self.sqli_redis.set('Vulnerable_urls', url)
            # print(self.sqli_redis.get("Vulnerable_urls"))
        except Exception as e:
            print(e)

    def is_finished(self):
        return self.finished




if __name__ == '__main__':
    # urls = ['http://testphp.vulnweb.com:80/listproducts.php?cat=1',
    #         'http://testphp.vulnweb.com:80/artists.php?artist=3',
    #         'http://testphp.vulnweb.com:80/comment.php?aid=3']
    save_pool = redis.ConnectionPool(host='127.0.0.1', port=6379, decode_responses=True)
    url = 'http://testphp.vulnweb.com'
    spider = SpiderMain(url, save_pool)
    print("开始启动")
    spider.run()
    SqliMain(spider.savepool)
