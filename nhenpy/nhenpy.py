import requests
import re
import shelve
import os
import hashlib
import zipfile
import threading
import queue
import shlex
import json
import pkg_resources

from bs4 import BeautifulSoup
import tqdm

class NHTags():
    _tag_store = json.loads(open(os.path.join(os.path.dirname(__file__), 'tags.transformed.json')).read())
    def __init__(self, nhe, tag_ids=[]):
        keys = []
        self._nhe = nhe
        self._complete = True
        if tag_ids:
            for tag in tag_ids:
                try:
                    x = self._tag_store[tag]
                    keys.append(x["tag"])
                    if x["tag"] in self.__dict__:
                        self.__dict__[x["tag"]].append(x["value"])
                    else:
                        self.__dict__[x["tag"]] = [x["value"]]
                except:
                    self._complete = False
        elif not self._nhe._tags:
                for label in nhe.get_labels():
                    x = label[1:-1].split("/")
                    keys.append(x[0])
                    if x[0] in self.__dict__:
                        self.__dict__[x[0]].append(x[1])
                    else:
                        self.__dict__[x[0]] = [x[1]]

        self.keys = list(set(keys))
    

    def __repr__(self):
        return f"<{'!' if not self._complete else ''}[{self._nhe.code}]{self._nhe.title} Tags: ({', '.join(self.keys)})>"


    def to_dict(self):
        return {x: self.__dict__[x] for x in self.keys}


class NHentaiDoujin():
    """
    Class NHentaiDoujin(doujin_code, title=None)
        Creates a nhentai doujin object.
    
    Parameters:
        code (required): Doujin code. ex.(/g/12345/, 12345, nhentai.net/g/12345/)
        title: Doujin title, usually used by the NHentai class

    """
    def __init__(self, code, title=None, tags=None):
        result = re.findall(r"g\/(\d*)", code)
        self.code = result[0] if result else code
        self.soup = None
        self._title = title
        if tags:
            self._tags = NHTags(self, tags)


    def _call_soup(self):
        if not self.soup:
            data = requests.get(f"https://nhentai.net/g/{self.code}/")
            self.soup = BeautifulSoup(data.text, "html.parser")


    @property
    def title(self):
        if self._title:
            return self._title

        self._call_soup()
        self._title = self.soup.find(id="info").find("h1").text
        return self._title


    def __repr__(self):
        title = self._title if self._title else "!unresolved!"
        return f"<[{self.code}]NHentaiDoujin: {title}>"


    @property
    def titles(self):
        self._call_soup()
        return [self.soup.find(id="info").find("h1").text, self.soup.find(id="info").find("h2").text]


    @property
    def pages(self):
        if "_images" not in self.__dict__:
            self.get_images()   

        return self._images

    def get_images(self):
        self._call_soup()
        gal_thumbs = [x.find("img")["data-src"] for x in self.soup.find_all("a", class_="gallerythumb")]
        self._images = []
        for i in gal_thumbs:
            x = i.replace("https://t.", "https://i.")
            filename = x.split("/")[-1]
            self._images.append(x.replace(filename, filename.replace("t", "")))
        return self._images


    @property
    def labels(self):
        if "_labels" not in self.__dict__:
            self.get_labels()

        return self._labels

    def get_labels(self):
        self._call_soup()
        flatten = lambda l: [item for sublist in l for item in sublist]
        self._labels = [x["href"] for x in flatten([y.find_all("a") for y in self.soup.find_all("span", class_="tags")])]
        return self._labels


    @property
    def info(self):
        if "_tags" not in self.__dict__:
            self._tags = NHTags(self)
        if not self._tags._complete:
            if self.soup:
                self._tags = NHTags(self)

        return self._tags

    def _sanitize(self, s):
        keepcharacters = " .[]_()@!#*-+"
        return "".join(c for c in s if c.isalnum() or c in keepcharacters).rstrip()


    def download_zip(self, **kwargs):
        """
        NHentaiDouhin.download_zip(**kwargs)
            Downloads the doujin into a zipfile

        Parameters
            **filename: Filename of the zip file. Defaults to a sanitized NHentaiDoujin.title.
            **path:   Folder where to save the zipfile. Defaults to the current working folder.
            **threads:  No of threads to spawn when downloading. Defaults to 8.
        """
        # Ensures that there's a title.
        images = self.get_images()
        filename = kwargs["filename"] if "filename" in kwargs else self._sanitize(self.title)+".zip"
        with zipfile.ZipFile(os.path.join(*[x for x in [kwargs.get("path"), filename] if x]), "w") as z:
            print(f"Downloading: {filename}")
            with tqdm.tqdm(total=len(images), unit="images") as progress:
                q = queue.Queue()
                for image in images:
                    q.put(image)

                work_threads = []
                for i in range(kwargs.get("threads", 8)):
                    t = NHentaiDownloadZipThread(q, z, progress)
                    t.setDaemon(True)
                    t.start()
                    work_threads.append(t)

                # Wait for the stuff to end.
                q.join()

                for t in work_threads:
                    # Shutdowns the threads.
                    t.running = False
                    del(t)

            print(f"Finished!")


    def download(self, **kwargs):
        """
        NHentaiDouhin.download(**kwargs)
            Downloads the doujin into a folder

        Parameters
            **filename: Filename of the zip file. Defaults to a sanitized NHentaiDoujin.title.
            **path:   Folder where to save the zipfile. Defaults to the current working folder.
            **threads:  No of threads to spawn when downloading. Defaults to 8.
        """
        # Ensures that there's a title.
        images = self.get_images()
        folder = kwargs["folder"] if "folder" in kwargs else self._sanitize(self.title)
        print(f"Downloading: {folder}")

        fullpath = os.path.join(*[x for x in [kwargs.get("path"), folder] if x])
        if not os.path.exists(fullpath):
            os.makedirs(fullpath)

        with tqdm.tqdm(total=len(images), unit="images") as progress:
            q = queue.Queue()
            for image in images:
                q.put(image)

            work_threads = []
            for i in range(kwargs.get("threads", 8)):
                t = NHentaiDownloadThread(q, folder, progress)
                t.setDaemon(True)
                t.start()
                work_threads.append(t)

            # Wait for the stuff to end.
            q.join()

            for t in work_threads:
                # Shutdowns the threads.
                t.running = False
                del(t)

        print(f"Finished!")


class NHentaiDownloadZipThread(threading.Thread):

    def __init__(self, queue, zipf, progress):
        threading.Thread.__init__(self)
        self.queue = queue
        self.zipf = zipf
        self.progress = progress
        self.running = True


    def run(self):
        while self.running:
            # grabs host from queue
            host = self.queue.get()
            filename = host.split("/")[-1]
            data = requests.get(host)
            with open("temp", "wb") as f:
                f.write(data.content)
            completed = False
            # I'll change this into something more elegant
            while not completed:
                try:
                    self.zipf.write("temp", filename)
                    completed = True
                except:
                    pass

            self.progress.update(1)
            # signals to queue job is done
            self.queue.task_done()


class NHentaiDownloadThread(threading.Thread):

    def __init__(self, queue, path, progress):
        threading.Thread.__init__(self)
        self.queue = queue
        self.path = path
        self.progress = progress
        self.running = True

    def run(self):
        while self.running:
            # grabs host from queue
            host = self.queue.get()
            filename = host.split("/")[-1]
            data = requests.get(host)
            with open(os.path.join(self.path, filename), "wb") as f:
                f.write(data.content)
            self.progress.update(1)
            # signals to queue job is done
            self.queue.task_done()


class QueryTag():
    def __init__(self, tag, value, include=True):
        self.tag = tag
        self.value = value
        self.include = include

    @classmethod
    def from_string(cls, string):
        include = True
        if string.startswith("-"):
            include = False
            string = string[1:]
        string = string.split(":")
        if len(string) != 2:
            #raise Exception("Malformed Tag string passed.")
            tag = "?"
            value = string[0]
        else:    
            tag = string[0]
            value = string[1]
            value = value.replace('"', '').replace("'", "").replace(" ", "-").lower()
            
        return cls(tag, value, include)

    def __repr__(self):
        return f"<[QueryTag]{self.tag}: {self.value}, include:{self.include}>"

    def __str__(self):
        if self.tag == "?":
            return self.value
        return f"{'-' if not self.include else ''}{self.tag}:{self.value}"
    
    def to_dict(self):
        return {"tag": self.tag, "value": self.value, "include": self.include}


class Query():

    def __init__(self, query_tags = []):
        self.tags = []
        if isinstance(query_tags, str):
            query_tags = shlex.split(query_tags)
        for i in query_tags:
            if not isinstance(i, QueryTag):
                i = QueryTag.from_string(i)
            self.tags.append(i)

    def __repr__(self):
        return f"<[Query]{self.build()}>"

    def __str__(self):
        return self.build()

    def add(self, query_tag):
        for i in shlex.split(query_tag):
            if not isinstance(i, QueryTag):
                i = QueryTag.from_string(i)
            self.tags.append(i)

    def build(self):
        return " ".join(str(x) for x in self.tags)


class Internal():
    tag_links = ["https://nhentai.net/tags/",
                 "https://nhentai.net/artists/",
                 "https://nhentai.net/characters/",
                 "https://nhentai.net/parodies/",
                 "https://nhentai.net/groups/"]

    def __init__(self):
        pass
    
    @classmethod
    def process_tags(self):
        tags = []
        for tag_link in self.tag_links:
            tags.extend(self.scrape_tags(tag_link))
        with open("tags.json", "w") as f:
            f.write(json.dumps(tags))
                
    @classmethod
    def scrape_tags(self, tag_link):
        p_tags = []
        current_page = 1
        while True:
            page = requests.get(tag_link+f"?page={current_page}")
            page = BeautifulSoup(page.text, "html.parser")
            tags = page.find_all(class_="tag")
            if len(tags) == 0:
                break
            for tag in tags:
                try:
                    tag_type, value = tag.get("href")[1:-1].split("/")
                    tag_id = tag.get("class")[1].split("-")[1]
                    tag_data = {"tag":tag_type, "value": value, "id": tag_id}
                    print(f"SUCCESS PROCESSING: {tag_data}")
                    p_tags.append(tag_data)
                except:
                    print(f"FAILED PROCESSING: {tag}")
            current_page += 1
        return p_tags
                
                


class NHentai():

    def __init__(self):
        self.search_endpoint = "https://nhentai.net/search/"
        self.cache_path = "cache.nhentai.net"
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)
        self.s = shelve.open(os.path.join(self.cache_path, "search_ssion.nh.net"), writeback=True)


    def extract(self, soup):
        data = soup.find_all(class_="gallery")
        result = {}
        for x in data:
            href = x.find(class_="cover").get("href")
            title = x.find(class_="cover").find(class_="caption").text
            tags = x.get("data-tags").split(" ")
            result.update({href: {"title": title, "tags": tags}})
        return result
        #return {x["href"]: x.find(class_="caption").text for x in data}

    def search(self, query, pages=0):
        if isinstance(query, Query):
            query = query.build()
        session_tag = f"search.{hashlib.md5(query.encode()).hexdigest()}.net"
        search_s = shelve.open(os.path.join(self.cache_path, session_tag), writeback=True)
        while True:
            current_page = search_s.get(f"current_page", 1)
            if "result" not in search_s:
                search_s["result"] = {}
            if current_page > pages and pages != 0:
                print("\n")
                break

            page = requests.get(self.search_endpoint, params={"q": query, "page": current_page})
            data = self.extract(BeautifulSoup(page.text, "html.parser"))
            if data is None:
                break
            if len(data) == 0:
                print("\n")
                break

            print(f"Seach Query: {query} -- Page [{current_page}] Items [{current_page * 25}]", end="\r")
            search_s["result"].update(data)
            current_page += 1
            search_s[f"current_page"] = current_page
            search_s.sync()


        result = [NHentaiDoujin(x, y["title"], y["tags"]) for x, y in search_s["result"].items()]
        search_s.close()

        return result