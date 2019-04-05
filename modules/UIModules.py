
import tornado.web

class Paginator(tornado.web.UIModule):
	def render(self, paginator):
		return self.render_string(
			"uimodule/paginator.htm", paginator = paginator)


class RepoMenu(tornado.web.UIModule):
	def render(self, repo, logined = None):
		return self.render_string(
			"uimodule/repomenu.htm", repo = repo, logined = logined)



