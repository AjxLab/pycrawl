import mechanize
import lxml.html
import re
from .carray import carray


class PyCrawl:
    def __init__(self, url: str = None, node: lxml.html.HtmlElement = None, html: str = None,
                 user_agent: str = None, timeout: int = 10, encoding: str = 'utf-8'):
        # set params
        self.url: str = url
        self.node: lxml.html.HtmlElement = node
        self.html: str = html
        self.user_agent: str = user_agent
        self.timeout: int = timeout
        self.encoding: str = encoding
        self.params: list = []
        self.tables: list = {}

        # create mechanize object
        self.agent = mechanize.Browser()
        self.agent.keep_alive = False
        self.agent.set_handle_refresh(False)
        self.agent.set_handle_equiv(False)
        self.agent.set_handle_robots(False)
        # set user agent
        if self.user_agent is not None:
            self.agent.addheaders = [('User-agent', user_agent)]

        # 1. set agent with URL
        if self.url is not None:
            self.get(self.url)
        # 2. set agent with node
        if self.node is not None:
            self.html = self.outer_text()
            self.__update_params(self.html)
        # 3. set agent with HTML
        if self.html is not None:
            self.__update_params(self.html)

    def get(self, url: str) -> None:
        """ access the target URL"""
        self.url = url
        page = self.agent.open(self.url, timeout=self.timeout)
        html = page.read().decode(self.encoding, 'ignore')
        self.__update_params(html)

    def send(self, **opts) -> None:
        """ set query params """
        # css selector: ["name", "id", "type", "nr", "label", "kind", "predicate"]
        params: dict = {}
        for selector, value in opts.items():
            params[selector] = value
        self.params.append(params)

    def submit(self, **opts) -> None:
        """ submit the form data """
        # css selector: ["id", "class_", "name", "nr"...]
        for selector, value in opts.items():
            # select form
            if isinstance(value, int):
                exec('self.agent.select_form(%s=%d)' % (selector, value))
            else:
                exec('self.agent.select_form(%s="%s")' % (selector, value))

        self.agent.form.set_all_readonly(False)

        for param in self.params:
            # テキスト，数値など
            if 'value' in param:
                value = param.pop('value')
                if value is None:
                    continue
                ctrl = self.__find_ctrl(**param)
                if ctrl is not None:
                    ctrl.value = value

            # チェックボックス
            if 'check' in param:
                check = param.pop('check')
                if check is None:
                    continue
                ctrl = self.__find_ctrl(**param)
                if ctrl is not None:
                    ctrl.selected = check

            # ファイルアップロード
            if 'file_name' in param:
                file_name = param.pop('file_name')
                if file_name is None:
                    continue
                ctrl = self.__find_ctrl(**param)
                if ctrl is not None:
                    ctrl.file_name = file_name

        # Submit
        self.agent.submit()
        self.__update_params(self.agent.response().read().decode(self.encoding, 'ignore'))

    def __find_ctrl(self, **attr):
        # --------------------------------------------
        # Controlを取得
        # params:
        #   - attr -> HTML attr（※ classは，class_と指定）
        # return:
        #   - mechanize._form_controls.xxxxControl
        # --------------------------------------------
        attr = {list(attr.items())[0][0].replace('_', ''): list(attr.items())[0][1]}
        try:
            return self.agent.form.find_control(**attr)
        except Exception:
            pass

        # 属性から検索
        for key, value in attr.items():
            for ctrl in self.agent.form.controls:
                if 'attrs' in vars(ctrl):
                    if key in ctrl.attrs:
                        if str(value) in str(ctrl.attrs[key]).split(' '):
                            return ctrl
                else:
                    try:
                        id = self.xpath('//*[@%s="%s"]' % (key, value)).attr('id')
                        return self.agent.form.find_control(id=id)
                    except Exception:
                        continue
        return None

    def xpath(self, locator, single=False):
        # --------------------------------------------
        # XPathを指定しノードを抽出
        # params:
        #   - locator:str -> XPath
        # return:
        #   - PyCrawl.carray
        # --------------------------------------------
        nodes = carray([PyCrawl(node=node) for node in self.node.xpath(locator)])
        if single:
            # シングルノード
            if nodes == []:
                return carray()
            else:
                return nodes[0]
        else:
            # 複数ノード
            return nodes

    def css(self, locator, single=False):
        # --------------------------------------------
        # CSSセレクタを指定しノードを抽出
        # params:
        #   - locator:str -> css selector
        # return:
        #   - PyCrawl.carray
        # --------------------------------------------
        nodes = carray([PyCrawl(node=node) for node in self.node.cssselect(locator)])
        if single:
            # シングルノード
            if nodes == []:
                return carray()
            else:
                return nodes[0]
        else:
            # 複数ノード
            return nodes

    def attr(self, attr: str) -> str:
        """ extract string of node attribute"""
        if attr in self.node.attrib:
            return self.node.attrib[attr]
        else:
            return ''

    def inner_text(self, shaping: bool = True) -> str:
        """ extract inner text"""
        if shaping:
            return self.__shaping_string(self.node.text_content())
        else:
            return self.node.text

    def outer_text(self) -> str:
        """ extract outer text"""
        result = lxml.html.tostring(self.node, encoding=self.encoding)
        result = result.decode(self.encoding, 'ignore')
        return result

    def __update_params(self, html: str) -> None:
        """ update self params"""
        if self.agent._response is None:
            self.url = ''
        else:
            self.url = self.agent.geturl()
        if html is None or html == '':
            html = '<html></html>'
        self.html = html
        self.node = lxml.html.fromstring(self.html)
        self.tables = self.__table_to_dict()

    def __table_to_dict(self) -> dict:
        """ convert <table> to dict"""
        result: dict = {}

        for tr in self.node.cssselect('tr'):
            if tr.cssselect('th') != [] and tr.cssselect('td') != []:
                key = self.__shaping_string(tr.cssselect('th')[0].text_content())
                value = self.__shaping_string(tr.cssselect('td')[0].text_content())
                result[key.replace('\n', '').replace(' ', '')] = value
        for dl in self.node.cssselect('dl'):
            if dl.cssselect('dt') != [] and dl.cssselect('dd') != []:
                key = self.__shaping_string(dl.cssselect('dt')[0].text_content())
                value = self.__shaping_string(dl.cssselect('dd')[0].text_content())
                result[key.replace('\n', '').replace(' ', '')] = value

        return result

    def __shaping_string(self, text: str) -> str:
        """ remove extra line breaks and whitespace """
        result = str(text)
        result = result.replace(' ', ' ')
        result = re.sub(r'\s+', ' ', result)
        result = result.replace('\n \n', '\n').replace('\n ', '\n').replace('\r', '\n')
        result = re.sub(r'\n+', '\n', result)
        return result.replace('\t', '').strip()
