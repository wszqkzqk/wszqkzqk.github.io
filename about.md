---
layout: page
title: "About"
description: "你好，我是星外之神."
header-img: "img/bg-3-darken.webp"
---

<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="330" height="86" src="//music.163.com/outchain/player?type=2&id=1868007999&auto=1&height=66"></iframe>

<div class="post-container" markdown="1">

> 合抱之木，生于毫末  
> 九层之台，起于累土  
> 千里之行，始于足下

你好，我是**星外之神**，在网络平台上的另一个常用名字是**wszqkzqk**。

- 🧪 **北京大学化学与分子工程学院**博士研究生
- 🐉 **[Arch Linux for Loong64 (或称 Loong Arch Linux)](https://github.com/lcpu-club/loongarch-packages)**（非官方的 Arch Linux 发行版 loong64 移植）项目社区负责人、维护者
- ✨ **[维基人](https://zh.wikipedia.org/wiki/User:%E6%98%9F%E5%A4%96%E4%B9%8B%E7%A5%9E)**
- 😉 目前是 **Arch Linux** 用户/开发者
  - 赞同 Linux 包管理器不区分"系统"和"一般软件"的哲学
  - 喜欢 pacman 的简洁设计
  - 喜欢滚动更新
- ✌️ **[Vala 编译器](https://gitlab.gnome.org/GNOME/vala)**外部贡献者
  - 经常在个人项目中使用 Vala
- 🐧 因维护发行版的缘故，其实什么语言都能写
- 🔧 维护一些实用小工具

这是我的个人博客，主要用于分享展示我的学习心得、个人经历以及感想

## 关于本站

### 我为什么要建这个网站

其实自初中以来，我一直都有建一个属于自己的网站的想法，但是囿于自己的能力水平、搭建网站所需要的诸如域名注册、服务器采用等繁琐的程序，以及维护所需要的精力或经济成本，一直没有实施。直到2020年初，我发现了[GitHub Pages](https://pages.github.com/)这一方便的途径，完美解决了域名和服务器的问题，我才借鉴、引用了大量现成的开源软件的代码，做了这个个人博客网站。

即使坐拥了很多现成的资源，搭建这个站对我来说也显得困难重重。初中就基本上不怎么了解HTML代码，现在过了好几年更是忘得一干二净。还好，博文的发布一般用方便简洁的Markdown就行，HTML其实仅仅需要用在几个主页之中。前人的贡献确实已经把我开发的工作量减到了最小，在这里我再次对[GitHub Pages](https://pages.github.com/)、[jekyll](http://jekyll.com.cn/)和[qiubaiying](http://qiubaiying.vip/)表示诚挚感谢。

### 我想要把这个网站建成什么样子、它将包含什么

这个网站是个人性质的博客，所以内容是比较杂乱的，在本网站搭建的**早期**，网站内容大多是我对**化学竞赛**学习的整理，但是此后内容比重发生了一些变化，网站内容涉及的领域变得更加广泛，也有了更多专属于我自己的内容。但不变的是，我依然会在我的网站中传达**我自己所喜欢或者敬佩**的内容。这些内容就目前来看主要涵盖**化学、知识共享和自由软件**，但也可能进一步变化。

这个网站既用于**给有需要的人提供方便**，又是一个**体现我个性的地方**。

### 本网站以后会有其他语言版本吗

目前来看不会。

### 我的GitHub

[![GitHub Profile](https://githubcard.com/wszqkzqk.svg?d=75sA8ArE)](https://github.com/wszqkzqk)

## 捐赠本站

如果您赞赏本网站的内容或愿意支持本网站的维护，欢迎捐赠！

<table style="table-layout: fixed; width: 100%;">
  <thead>
    <tr>
      <th style="text-align: center; width: 50%;"><strong>支付宝</strong></th>
      <th style="text-align: center; width: 50%;"><strong>微信支付</strong></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="text-align: center;"><a href="/img/donate-alipay.webp"><img src="/img/donate-alipay.webp" alt="支付宝" /></a></td>
      <td style="text-align: center;"><a href="/img/donate-wechatpay.webp"><img src="/img/donate-wechatpay.webp" alt="微信支付" /></a></td>
    </tr>
  </tbody>
</table>

</div>

<!-- Gitalk 评论 start -->
{% if site.gitalk.enable %}
<!-- Gitalk link -->
<link rel="stylesheet" href="https://unpkg.com/gitalk/dist/gitalk.css">
<script src="https://unpkg.com/gitalk@latest/dist/gitalk.min.js"></script>
<div id="gitalk-container"></div>
<script type="text/javascript">
    var gitalk = new Gitalk({
        clientID: '{{site.gitalk.clientID}}',
        clientSecret: '{{site.gitalk.clientSecret}}',
        repo: '{{site.gitalk.repo}}',
        owner: '{{site.gitalk.owner}}',
        admin: ['{{site.gitalk.admin}}'],
        distractionFreeMode: {{site.gitalk.distractionFreeMode}},
        id: 'about',
    });
    gitalk.render('gitalk-container');
</script>
{% endif %}
<!-- Gitalk end -->

<!-- disqus 评论框 start -->
{% if site.disqus.enable %}
<div class="comment">
    <div id="disqus_thread" class="disqus-thread">
    </div>
</div>
<!-- disqus 评论框 end -->
<!-- disqus 公共JS代码 start (一个网页只需插入一次) -->
<script type="text/javascript">
    /* * * CONFIGURATION VARIABLES * * */
    var disqus_shortname = "{{site.disqus.username}}";
    var disqus_identifier = "{{site.disqus.username}}/{{page.url}}";
    var disqus_url = "{{site.url}}{{page.url}}";
    (function() {
        var dsq = document.createElement('script'); dsq.type = 'text/javascript'; dsq.async = true;
        dsq.src = '//' + disqus_shortname + '.disqus.com/embed.js';
        (document.getElementsByTagName('head')[0] || document.getElementsByTagName('body')[0]).appendChild(dsq);
    })();
</script>
<!-- disqus 公共JS代码 end -->
{% endif %}

本站未注明授权的博文默认采用[署名标示（BY）-非商业性（NC）-禁止演绎（ND）-4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/deed.zh)协议共享
