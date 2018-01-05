import requests
import re
import shelve
import os
import hashlib
import zipfile
import threading
import queue

from bs4 import BeautifulSoup
import tqdm

class NHTags():

    def __init__(self, nhe):
        keys = []
        self._nhe = nhe
        for label in nhe.get_labels():
            x = label.split("/")
            keys.append(x[1])
            if x[1] in self.__dict__:
                self.__dict__[x[1]].append(x[2])
            else:
                self.__dict__[x[1]] = [x[2]]

        self.keys = list(set(keys))


    def __repr__(self):
        return f"<[{self._nhe.code}]{self._nhe.title} Tags: ({', '.join(self.keys)})>"


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
    def __init__(self, code, title=None):
        result = re.findall(r"g\/(\d*)", code)
        self.code = result[0] if result else code
        self.soup = None
        self._title = title


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




class NHentai():

    def __init__(self):
        self.search_endpoint = "https://nhentai.net/search/"
        self.cache_path = "cache.nhentai.net"
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)
        self.s = shelve.open(os.path.join(self.cache_path, "search_ssion.nh.net"), writeback=True)


    def extract(self, soup):
        data = soup.find_all(class_="cover")
        return {x["href"]: x.find(class_="caption").text for x in data}


    def search(self, query, pages=0):
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
            if len(data) == 0:
                print("\n")
                break

            print(f"Seach Query: {query} -- Page [{current_page}] Items [{current_page * 25}]", end="\r")
            search_s["result"].update(data)
            current_page += 1
            search_s[f"current_page"] = current_page
            search_s.sync()


        result = [NHentaiDoujin(x, y) for x, y in search_s["result"].items()]
        search_s.close()

        return result