# encoding:utf-8
import time
import requests
import os
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
import plugins
from plugins import *

def check_prefix(content, prefix_list):
    prefix_list = eval(prefix_list)
    if not prefix_list:
        return False, None
    for prefix in prefix_list:
        if content.startswith(prefix):
            return True, content.replace(prefix, "").strip()
    return False, None

@plugins.register(
    name="MidJourney",
    desc="一款AI绘画工具",
    version="1.0.0",
    author="mouxan"
)
class MidJourney(Plugin):
    def __init__(self):
        try:
            super().__init__()
            # 不可与image_create_prefix重复，image_create_prefix优先级更高
            self.help_prefix = os.environ.get("help_prefix", ["/mjhp", "/mjhelp"])
            self.imagine_prefix = os.environ.get("imagine_prefix", ["/mj", "/imagine", "/img"])
            self.fetch_prefix = os.environ.get("fetch_prefix", ["/ft", "/fetch"])
            self.mj_url = os.environ.get("mj_url", None)
            mj_api_secret = os.environ.get("mj_api_secret", None)
            if not self.mj_url:
                logger.warn(f"[MJ] init failed, 未配置[mj_url].")
            self.mj = _mjApi(self.mj_url, mj_api_secret)
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info("[MJ] inited. mj_url={} mj_api_secret={}".format(self.mj_url, self.mj_api_secret))
        except Exception as e:
            logger.warn("[MJ] init failed." + str(e))
            raise e

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
        ]:
            return

        channel = e_context['channel']
        context = e_context['context']
        content = context.content

        hprefix = check_prefix(content, self.help_prefix)
        logger.info("[MJ] hprefix={}".format(hprefix))
        iprefix, iq = check_prefix(content, self.imagine_prefix)
        logger.info("[MJ] iprefix={} iq={}".format(iprefix,iq))
        fprefix, fq = check_prefix(content, self.fetch_prefix)
        logger.info("[MJ] fprefix={} fq={}".format(fprefix,fq))
        if hprefix == True:
            channel._handle(Reply(ReplyType.TEXT, "测试数据"), context)
            reply = Reply(ReplyType.TEXT, self.mj.help_text())
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS  # 事件结束，并跳过处理context的默认逻辑
            return
        elif iprefix == True or content.startswith("/up"):
            if not self.mj_url:
                reply = Reply(ReplyType.ERROR, "服务器环境变量未配置[mj_url]")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            reply = None
            if iprefix == True:
                status, msg, id = self.mj.imagine(iq)
            else:
                status, msg, id = self.mj.simpleChange(content.replace("/up", "").strip())
            if status:
                channel._send(Reply(ReplyType.INFO, msg), context)
                status2, msgs, imageUrl = self.mj.get_f_img(id)
                if status2:
                    channel._send(Reply(ReplyType.TEXT, msgs), context)
                    reply = Reply(ReplyType.IMAGE_URL, imageUrl)
                else:
                    reply = Reply(ReplyType.ERROR, msgs)
            else:
                reply = Reply(ReplyType.ERROR, msg)
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return
        elif fprefix == True:
            if not self.mj_url:
                reply = Reply(ReplyType.ERROR, "服务器环境变量未配置[mj_url]")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            status, msg, imageUrl = self.mj.fetch(fq)
            reply = None
            if status:
                channel._send(Reply(ReplyType.TEXT, msg), context)
                if imageUrl:
                    reply = Reply(ReplyType.IMAGE_URL, imageUrl)
            else:
                reply = Reply(ReplyType.ERROR, msg)
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return


    def get_help_text(self, isadmin=False, isgroup=False, verbose=False,**kwargs):
        if kwargs.get("verbose") != True:
            return "这是一个AI绘画工具，只要输入想到的文字，通过人工智能产出相对应的图。"
        else:
            return self.mj.help_text()

class _mjApi:
    def __init__(self, mj_url, mj_api_secret):
        self.baseUrl = mj_url
        self.headers = {
            "Content-Type": "application/json",
        }
        if mj_api_secret:
            self.headers["mj-api-secret"] = mj_api_secret
    
    def imagine(self, text):
        try:
            url = self.baseUrl + "/mj/submit/imagine"
            data = {"prompt": text}
            res = requests.post(url, json=data, headers=self.headers)
            code = res.json()["code"]
            if code == 1:
                msg = "✅ 您的任务已提交\n"
                msg += f"🚀 正在快速处理中，请稍后\n"
                msg += f"📨 任务ID: {res.json()['result']}\n"
                msg += f"🪄 查询进度\n"
                msg += f"✏  使用[/fetch + 任务ID操作]\n"
                msg += f"/fetch {res.json()['result']}"
                return True, msg, res.json()["result"]
            else:
                return False, res.json()["description"]
        except Exception as e:
            return False, "图片生成失败"
    
    def simpleChange(self, content):
        try:
            url = self.baseUrl + "/mj/submit/simple-change"
            data = {"content": content}
            res = requests.post(url, json=data, headers=self.headers)
            code = res.json()["code"]
            if code == 1:
                msg = "✅ 您的任务已提交\n"
                msg += f"🚀 正在快速处理中，请稍后\n"
                msg += f"📨 任务ID: {res.json()['result']}\n"
                msg += f"🪄 查询进度\n"
                msg += f"✏  使用[/fetch + 任务ID操作]\n"
                msg += f"/fetch {res.json()['result']}"
                return True, msg, res.json()["result"]
            else:
                return False, res.json()["description"]
        except Exception as e:
            return False, "图片生成失败"
    
    def fetch(self, id):
        try:
            url = self.baseUrl + f"/mj/task/{id}/fetch"
            res = requests.get(url, headers=self.headers)
            status = res.json()['status']
            startTime = ""
            finishTime = ""
            if res.json()['startTime']:
                startTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(res.json()['startTime']/1000))
            if res.json()['finishTime']:
                finishTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(res.json()['finishTime']/1000))
            msg = "✅ 查询成功\n"
            msg += f"任务ID: {res.json()['id']}\n"
            msg += f"描述内容：{res.json()['prompt']}\n"
            msg += f"状态：{self.status(status)}\n"
            msg += f"进度：{res.json()['progress']}\n"
            if startTime:
                msg += f"开始时间：{startTime}\n"
            if finishTime:
                msg += f"完成时间：{finishTime}\n"
            if res.json()['imageUrl']:
                return True, msg, res.json()['imageUrl']
            return True, msg, None
        except Exception as e:
            return False, "查询失败"
    
    def status(self, status):
        msg = ""
        if status == "SUCCESS":
            msg = "已成功"
        elif status == "FAILURE":
            msg = "失败"
        elif status == "SUBMITTED":
            msg = "已提交"
        elif status == "IN_PROGRESS":
            msg = "处理中"
        else:
            msg = "未知"
        return msg
    
    def get_f_img(self, id):
        try:
          url = self.baseUrl + f"/mj/task/{id}/fetch"
          status = ""
          rj = ""
          while status != "SUCCESS":
              time.sleep(3)
              res = requests.get(url, headers=self.headers)
              rj = res.json()
              status = rj["status"]
          action = rj["action"]
          msg = ""
          if action == "IMAGINE":
              msg = f"🎨 绘图成功\n"
              msg += f"✨ 内容: {rj['prompt']}\n"
              msg += f"✨ 内容: {rj['prompt']}\n"
              msg += f"📨 任务ID: {id}\n"
              msg += f"🪄 放大 U1～U4，变换 V1～V4\n"
              msg += f"✏ 使用[/up 任务ID 操作]\n"
              msg += f"/up {id} U1"
          elif action == "UPSCALE":
              msg = "🎨 放大成功\n"
              msg += f"✨ {rj['description']}\n"
          return True, msg, rj["imageUrl"]
        except Exception as e:
            return False, "绘图失败"
    
    def help_text(self):
        help_text = "欢迎使用MJ机器人\n"
        help_text += f"这是一个AI绘画工具，只要输入想到的文字，通过人工智能产出相对应的图。\n"
        help_text += f"------------------------------\n"
        help_text += f"🎨 AI绘图-使用说明：\n"
        help_text += f"输入: /mj prompt\n"
        help_text += f"prompt 即你提的绘画需求\n"
        help_text += f"------------------------------\n"
        help_text += f"📕 prompt附加参数 \n"
        help_text += f"1.解释: 在prompt后携带的参数, 可以使你的绘画更别具一格\n"
        help_text += f"2.示例: /mj prompt --ar 16:9\n"
        help_text += f"3.使用: 需要使用--key value, key和value空格隔开, 多个附加参数空格隔开\n"
        help_text += f"------------------------------\n"
        help_text += f"📗 附加参数列表\n"
        help_text += f"1. --v 版本 1,2,3,4,5 默认5, 不可与niji同用\n"
        help_text += f"2. --niji 卡通版本 空或5 默认空, 不可与v同用\n"
        help_text += f"3. --ar 横纵比 n:n 默认1:1\n"
        help_text += f"4. --q 清晰度 .25 .5 1 2 分别代表: 一般,清晰,高清,超高清,默认1\n"
        help_text += f"5. --style 风格 (4a,4b,4c)v4可用 (expressive,cute)niji5可用\n"
        help_text += f"6. --s 风格化 1-1000 (625-60000)v3"
        return help_text