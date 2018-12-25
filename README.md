Let's do this!


v1.0版本：
part one:
    在Proxy类中增加了两个变量：self.Read和self.first_time，两个变量均为bool类型。
    之前出现的问题是，在处理请求一个网站的request的时候，因为我们有多个request，同时这些网站里边可能会有一样的地址头。这样就会导致在第二次request的时候就会读取缓存，而实际上我们要请求的东西并不是缓存里边的。
    所以要解决这个问题，我设计了以下思路：
    if 这是一个proxy第一次发送请求:
        if 缓存中有这个地址:
            self.Read=True     //表示我这次是可以读缓存的
            读缓存
        else:
            self.Read=False
            self.server.recv()      //同以前
    else:
        if self.Read:                //表示我这次是可以读缓存的
            看看缓存中有没有，有就读，没有就从server获得
        else
            直接发请求从server获得
    
   这个的原理大概是这样的：如果这是我第一次发请求，那么如果缓存中有，那我之后也可以在缓存里边找；如果缓存中没有，那说明以后内容应该也是缓存中没有的，那么以后就不能读缓存。
   
 part two:
    读缓存的操作在process_rlist中实现（v1.0 503行开始）。添加了flag变量判断本次操作是读取了缓存还是从服务器获取信息。
    if server 已经连接且没有关闭
        在buffer寻找有无缓存
        若有，flag 为 True ，反之则为False
    在之后542行 self._process_response(data,flag)中会进行保存缓存的操作
    432行往后，若not flag成立，才会创建缓存（即确认此次的信息是新的而非从缓存中获取的，避免内存爆炸）。

log_in_page.html:
naive log in page

登录注册页面操作流程：
1.python proxy.py(目前第56行app.run默认参数是127.0.0.1和5000，可根据实际情况改成app.run(host=***,port=***))
2.如未注册，浏览器打开127.0.0.1:5000/register(在联网未开proxy状态下)进行注册，注册成功后会自动跳转到登陆界面。
  如已注册，浏览器打开127.0.0.1:5000/login进行登录。
3.python proxy_tian_v1.0.py，即可使用proxy。


v1.1增加了离线读取缓存
首先注释掉了403行，这样server无法连接时不会抛出错误
process_rlist里，将整个判断是否读取buffer的部分放到了if self.server and not self.server.closed and self.server.conn in r:这个判断的外面，也就是说不管怎样都会先找buffer，如果找到了buffer，就使用buffer获取data，之后处理，直接return False（503~527行）。这样就完全忽略了与服务器相关的所有操作，离线读取了buffer。
