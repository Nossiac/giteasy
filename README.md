# Welcome to Giteasy

------

### What it is

[Giteasy](https://github.com/nossiac/giteasy) is a simple web service for your git repositories.

Features:

- Share your repository via HTTP(s).
- Basic authentication and user management.
- Basic repository management.
- Basic webhooks to integrate with external CI system.

A working demo can be found [Here](http://git.nossiac.com)

It is built mainly on top of [tornado](https://github.com/tornadoweb/tornado) and [pygit2](https://github.com/libgit2/pygit2).

### Install and run

	git clone https://github.com/nossiac/giteasy
	cd giteasy
	pip3 install -r requirements.txt
	python3 giteasy.py

### Why do you make another git service?

I was trying to setup a git server with web frontend for my team on an old PC. I chose gitlab, it's awesome. But unfortunately it didn't work becuase it turned out that gitlab requires too much resource to run.

From that moment, I start to considering writting my own git web server.

Why not? I'm interested, and I'm sure I can.

So, here it is.