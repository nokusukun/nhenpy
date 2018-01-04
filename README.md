# nhenpy
---
A python library for searching and downloading in nhentai.net

### Requirements
 * requests
 * bs4 (BeautifulSoup)
 * tqdm


### Usage
---
To search, just call up `NHentai().search()`

    ```python
    >>> from nhenpy import nhenpy
    >>> nh = nhenpy.NHentai()
    >>> search = nh.search("language:english", 1)
    Seach Query: language:english -- Page [1] Items [25]
    >>> 
    >>> search[0]
    <[/g/218906/]NHentaiDoujin: [Yaminabe] Ikutoshi Dasutoshi (Loliota) [English] [BlindEye]>
    >>> 
    >>> search[0].title
    '[Yaminabe] Ikutoshi Dasutoshi (Loliota) [English] [BlindEye]'
    >>> 
    >>> len(search[0].pages)
    28
    >>> 
    >>> search[0].info
    <[/g/218906/][Yaminabe] Ikutoshi Dasutoshi (Loliota) [English] [BlindEye] Tags: (category, language, artist, tag)>
    >>> 
    >>> search[0].info.tag
    ['lolicon', 'glasses', 'sole-female', 'sole-male', 'nakadashi', 'sumata']
    >>> 
    >>> search[0].info.artist
    ['yaminabe']
    >>> 
    >>> search[0].info.category
    ['manga']
    >>> 
    >>> search[0].download_zip()
    Downloading: [Yaminabe] Ikutoshi Dasutoshi (Loliota) [English] [BlindEye].zip
    100%|██████████████████████████████████████████████████████████████████████████████| 28/28 [01:43<00:00,  2.59s/images] Finished!```


To just create a single doujin object, create a `nhenpy.NHentaiDoujin` object.

    ```python
    >>> doujin = nhenpy.NHentaiDoujin("/g/218906")
    >>> doujin
    <[/g/218906]NHentaiDoujin: !unresolved!>
    >>> doujin.title
    'Ikutoshi Dasutoshi'
    >>> doujin
    <[/g/218906]NHentaiDoujin: Ikutoshi Dasutoshi>
    >>>```