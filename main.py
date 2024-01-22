from flask import Flask, request, send_file, jsonify
import base64
import io
import requests
import re
import wordcloud
import time
import matplotlib.pyplot as plt
from flask_cors import CORS
from datetime import datetime, timedelta


def generate_wc(text, image_name):
  # 设置词云的字体路径，这里使用微软雅黑
  font_path = 'FZYTK.TTF'
  # 使用jieba进行中文分词

  # 实例化词云
  # 自定义的屏蔽词
  my_stop_words = {
      'doge', 'amp', 'amps', 'amper', 'amperf', 'amperfi', 'amperfin', 'amper'
  }
  wc = wordcloud.WordCloud(font_path=font_path,
                           width=1920,
                           height=1080,
                           background_color='white',
                           stopwords=wordcloud.STOPWORDS
                           | my_stop_words).generate(text)

  # 使用 Matplotlib 显示词云
  plt.figure(figsize=(10, 5))
  plt.imshow(wc, interpolation='bilinear')
  plt.axis("off")

  # 保存成图片
  plt.savefig(image_name, dpi=500)


def extract(pattern, content):
  result = re.search(pattern, content)
  if result:
    return result.group(1)
  return None


def get_response(url):
  headers = {
      "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
  }
  try:
    r = requests.get(url, headers=headers)
    r.encoding = 'utf-8'
    return r
  except requests.exceptions.RequestException as e:
    print("请求发生异常:", e)
    return None


class Bilibili:

  def __init__(self, url, only_comment, only_barrage):
    self.info = None  # 保存视频的热度数据
    self.aid = None  # av号
    self.cid = None  # cv号
    self.comment_list = None  # 评论列表
    self.barrage_list = None  # 弹幕列表
    self.max_pn = 20  # 最大评论页数
    self.html = get_response(url).text  # url 对应的 html 内容
    print("访问url成功")
    self.get_info_and_ids()  # 从 html 中获取一些信息，包括 aid 和 cid
    print("信息提取成功")
    if only_comment:
      self.get_comment()  # 获取评论
      print("成功获取评论")
    if only_barrage:
      self.get_barrage()  # 获取弹幕
      print("成功获取弹幕")

  # 使用api获取弹幕
  def get_barrage(self):
    barrage_url = 'https://comment.bilibili.com/' + self.cid + '.xml'
    barrage = get_response(barrage_url).text

    # 正则表达式匹配字幕文本
    self.barrage_list = list(
        map(lambda s: s.replace(" ", ""), re.findall('">(.*?)</d>', barrage)))

  # 使用api获取评论
  def get_comment(self):
    # 从 1 开始
    pn = 1
    self.comment_list = []
    while True:
      try:
        # https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/comment/list.md
        r = get_response(
            'https://api.bilibili.com/x/v2/reply?pn={}&type=1&oid={}&sort=2'.
            format(pn, self.aid)).json()
        replies = r['data']['replies']
        for reply in replies:
          self.comment_list.append(reply['content']['message'])
        pn += 1
        if pn > self.max_pn:
          break
      except Exception:
        break

  # 从html中提取一些信息，包括cid和aid
  def get_info_and_ids(self):
    # 提取 aid 和 cid
    # aid（Audio Video ID，AV 号）用于表示特定的视频。每个上传到 Bilibili 的视频都会被赋予一个唯一的 aid，用于在平台上识别这个视频。
    # cid（Content ID）代表内容标识符，用于指定视频中的特定内容，如单独的一集或视频的某个特定部分。
    # aid 用于标识整个视频，而 cid 用于标识视频中的具体内容或章节
    # bvid（BV号）：这是一个独特的字符串，用于唯一标识 Bilibili 上的一个视频,bvid 是 Bilibili 的一个较新的视频标识系统，它与 aid 功能类似，都是用于在平台上唯一标识一个视频，但 bvid 提供了更高的安全性和隐私保护
    self.cid = extract(r'{"cid":([\d]+),"page":1', self.html)
    self.aid = extract(r'"aid":([\d]+),', self.html)
    # 使用正则表达式提取所需信息
    pattern = r"视频播放量 (\d+)、弹幕量 (\d+)、点赞数 (\d+)、投硬币枚数 (\d+)、收藏人数 (\d+)、转发人数 (\d+), 视频作者 (.*?), "
    match = re.search(pattern, self.html)

    # 提取时间字符串
    time_str = extract(
        r'<span class="pubdate".*?\n\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\n\s*',
        self.html)
    # 将字符串转换为datetime对象
    time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    # 考虑到时区差（例如UTC+8）
    time_obj_utc = time_obj - timedelta(hours=8)
    # 将datetime对象转换为时间戳
    timestamp_seconds = int(time.mktime(time_obj_utc.timetuple()))
    timestamp_milliseconds = timestamp_seconds * 1000

    # 提取评论量的
    reply_pattern = r'"reply":(.*?),"'
    reply_match = re.search(reply_pattern, self.html)

    # 提取标题的
    title_pattern = r'<meta data-vue-meta="true" itemprop="name" name="title" content="(.*?)_哔哩哔哩_bilibili">'
    title_match = re.search(title_pattern, self.html)

    # 检查是否匹配并提取结果
    self.info = {
        "viewCount": int(match.group(1)),
        "danmuCount": int(match.group(2)),
        "likeCount": int(match.group(3)),
        "coinCount": int(match.group(4)),
        "collectionCount": int(match.group(5)),
        "shareCount": int(match.group(6)),
        "uploader": match.group(7),
        "releaseTime": timestamp_milliseconds,
        "commentCount": int(reply_match.group(1)) if reply_match else 0,
        "title": title_match.group(1) if title_match else ""
    }


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config['CORS_ALLOW_ORIGINS'] = '*'
app.config['CORS_ALLOW_METHODS'] = ['GET', 'POST']
app.config['CORS_ALLOW_HEADERS'] = ['Content-Type', 'Authorization']


# 1. b站视频基本数据
@app.route('/get_bilibili_data', methods=['POST'])
def get_bilibili_data():
  # 使用 request.form 来获取表单数据
  video_url = request.form.get('video_url')
  print(video_url)

  if not video_url:
    return jsonify({"error": "No video URL provided"}), 400

  # 使用提供的类和函数处理视频
  bilibili = Bilibili(video_url, False, False)
  # 返回数据和图像
  return jsonify({"status": 200, "info": bilibili.info})


# 2. 评论词云
@app.route('/generate_comment_wordcloud', methods=['POST'])
def generate_comment_wordcloud():
  # 使用 request.form 来获取表单数据
  video_url = request.form.get('video_url')
  if not video_url:
    return jsonify({"error": "No video URL provided"}), 400

  # 使用 Bilibili 类处理视频
  bilibili = Bilibili(video_url, True, False)
  print(bilibili.comment_list)
  # 将评论词云图像保存到内存
  buffer = io.BytesIO()
  generate_wc("".join(bilibili.comment_list), buffer)
  buffer.seek(0)  # 重置文件指针到开始位置

  # 发送评论词云图像
  return send_file(buffer,
                   mimetype='image/png',
                   as_attachment=True,
                   download_name="comment_wordcloud.png")


# 3. 弹幕词云
@app.route('/generate_barrage_wordcloud', methods=['POST'])
def generate_barrage_wordcloud():
  # 使用 request.form 来获取表单数据
  video_url = request.form.get('video_url')
  if not video_url:
    return jsonify({"error": "No video URL provided"}), 400

  # 使用 Bilibili 类处理视频
  bilibili = Bilibili(video_url, False, True)

  # 将弹幕词云图像保存到内存
  print(bilibili.barrage_list)
  buffer = io.BytesIO()
  generate_wc("".join(bilibili.barrage_list), buffer)
  buffer.seek(0)  # 重置文件指针到开始位置

  # 发送弹幕词云图像
  return send_file(buffer,
                   mimetype='image/png',
                   as_attachment=True,
                   download_name="barrage_wordcloud.png")


app.run(host='0.0.0.0', port=81)
