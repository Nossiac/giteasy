import os
import sys
import signal

import markdown
import bleach
from bleach_whitelist import markdown_tags, markdown_attrs


def admin(func):
	def _wrapper(self, *args, **kwargs):
		user = self.current_user
		if not user:
			return self.redirect("/!login?next="+self.request.uri)
		else:
			if user.admin():
				return func(self, *args, **kwargs)
			else:
				return self.info("Not authorized!")
	return _wrapper


def safe_markdown(text):
	return bleach.clean(markdown.markdown(text), markdown_tags, markdown_attrs)






def daemonize(logfile="giteasy.log"):

	def freopen(f, mode, stream):
		oldf = open(f, mode)
		oldfd = oldf.fileno()
		newfd = stream.fileno()
		os.close(newfd)
		os.dup2(oldfd, newfd)

	def handle_exit(signum, _):
		if signum == signal.SIGTERM:
			sys.exit(0)
		sys.exit(1)

	signal.signal(signal.SIGINT, handle_exit)
	signal.signal(signal.SIGTERM, handle_exit)

	# fork only once because we are sure parent will exit
	pid = os.fork()
	assert pid != -1

	if pid > 0:
		# parent waits for its child
		time.sleep(5)
		sys.exit(0)

	# child signals its parent to exit
	ppid = os.getppid()
	pid = os.getpid()

	os.setsid()
	signal.signal(signal.SIGHUP, signal.SIG_IGN)

	os.kill(ppid, signal.SIGTERM)

	sys.stdin.close()
	if not logfile: return
	try:
		freopen(logfile, 'a', sys.stdout)
		freopen(logfile, 'a', sys.stderr)
	except IOError as e:
		shell.print_exception(e)
		sys.exit(1)
