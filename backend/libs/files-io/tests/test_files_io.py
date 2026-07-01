"""Integration tests for files_io module."""

import os
import tempfile
import pytest

import rust_io.files as files_io


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestFileReadWrite:
    def test_write_and_read_bytes(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.bin")
        f = files_io.File(path)
        f.write(b"hello world")
        assert f.read() == b"hello world"

    def test_write_and_read_text(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        f = files_io.File(path)
        f.write("hello world")
        assert f.read(as_text=True) == "hello world"

    def test_context_manager(self, tmp_dir):
        path = os.path.join(tmp_dir, "ctx.txt")
        with files_io.File(path) as f:
            f.write("context test")
        assert f.read(as_text=True) == "context test"


class TestFileMetadata:
    def test_metadata_returns_dict(self, tmp_dir):
        path = os.path.join(tmp_dir, "meta.txt")
        f = files_io.File(path)
        f.write("metadata test")
        meta = f.metadata()
        assert isinstance(meta, dict)
        assert meta["size"] == len(b"metadata test")
        assert meta["is_file"] is True
        assert meta["is_dir"] is False
        assert "mtime" in meta
        assert "permissions" in meta


class TestFileOperations:
    def test_exists(self, tmp_dir):
        path = os.path.join(tmp_dir, "exists.txt")
        f = files_io.File(path)
        assert not f.exists()
        f.write("exists")
        assert f.exists()

    def test_rename(self, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "dst.txt")
        f = files_io.File(src)
        f.write("rename me")
        f.rename(dst)
        assert not f.exists()
        assert files_io.File(dst).read(as_text=True) == "rename me"

    def test_copy(self, tmp_dir):
        src = os.path.join(tmp_dir, "copy_src.txt")
        dst = os.path.join(tmp_dir, "copy_dst.txt")
        f = files_io.File(src)
        f.write("copy me")
        f.copy(dst)
        assert f.read(as_text=True) == "copy me"
        assert files_io.File(dst).read(as_text=True) == "copy me"

    def test_remove(self, tmp_dir):
        path = os.path.join(tmp_dir, "remove.txt")
        f = files_io.File(path)
        f.write("remove me")
        assert f.exists()
        f.remove()
        assert not f.exists()

    def test_list_dir(self, tmp_dir):
        for name in ["a.txt", "b.txt", "c.txt"]:
            files_io.File(os.path.join(tmp_dir, name)).write("x")
        entries = files_io.File(tmp_dir).list_dir()
        assert set(entries) == {"a.txt", "b.txt", "c.txt"}


class TestContentHash:
    def test_same_content_same_hash(self, tmp_dir):
        p1 = os.path.join(tmp_dir, "h1.txt")
        p2 = os.path.join(tmp_dir, "h2.txt")
        files_io.File(p1).write("same content")
        files_io.File(p2).write("same content")
        assert files_io.File(p1).content_hash() == files_io.File(p2).content_hash()

    def test_different_content_different_hash(self, tmp_dir):
        p1 = os.path.join(tmp_dir, "h1.txt")
        p2 = os.path.join(tmp_dir, "h2.txt")
        files_io.File(p1).write("content A")
        files_io.File(p2).write("content B")
        assert files_io.File(p1).content_hash() != files_io.File(p2).content_hash()


class TestArchive:
    def test_zip_compress_extract(self, tmp_dir):
        src_dir = os.path.join(tmp_dir, "src")
        os.makedirs(src_dir)
        files_io.File(os.path.join(src_dir, "a.txt")).write("file a")
        files_io.File(os.path.join(src_dir, "b.txt")).write("file b")
        archive = os.path.join(tmp_dir, "test.zip")
        count = files_io.File(src_dir).compress(archive, "zip")
        assert count == 2
        out_dir = os.path.join(tmp_dir, "out_zip")
        count = files_io.File(archive).extract(out_dir)
        assert count >= 2
        assert files_io.File(os.path.join(out_dir, "a.txt")).read(as_text=True) == "file a"

    def test_tar_gz_compress_extract(self, tmp_dir):
        src_dir = os.path.join(tmp_dir, "src_tgz")
        os.makedirs(src_dir)
        files_io.File(os.path.join(src_dir, "x.txt")).write("file x")
        archive = os.path.join(tmp_dir, "test.tar.gz")
        count = files_io.File(src_dir).compress(archive, "tar.gz")
        assert count == 1
        out_dir = os.path.join(tmp_dir, "out_tgz")
        count = files_io.File(archive).extract(out_dir)
        assert count >= 1


class TestDedup:
    def test_check_duplicate(self, tmp_dir):
        p1 = os.path.join(tmp_dir, "d1.txt")
        p2 = os.path.join(tmp_dir, "d2.txt")
        files_io.File(p1).write("duplicate content")
        files_io.File(p2).write("duplicate content")
        h1 = files_io.File(p1).content_hash()
        result = files_io.check_duplicate(p2, [h1])
        assert result["is_duplicate"] is True

    def test_batch_hash(self, tmp_dir):
        paths = []
        for i in range(3):
            p = os.path.join(tmp_dir, f"batch_{i}.txt")
            files_io.File(p).write(f"content {i}")
            paths.append(p)
        result = files_io.batch_hash(paths)
        assert len(result["hashes"]) == 3
        assert len(result["errors"]) == 0
