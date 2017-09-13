#!/usr/bin/env python3
import tornado.web

def stringify(x):
    if x is None or isinstance(x, str):
        return x
    elif isinstance(x, bytes):
        return x.decode()
    else:
        return str(x)

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return "1"
        return stringify(self.get_secure_cookie("user"))

    def render(self, template_name, **kwargs):
            tornado.web.RequestHandler.render(self,
                    template_name,
                    current_user = self.current_user,
                    **kwargs
            )
