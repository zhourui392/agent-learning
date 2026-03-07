"""
关键词召回器：基于 BM25 的关键词检索。

生产环境对接 ElasticSearch，当前为内存 BM25 mock 实现。
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IndexedChunk:
    """已索引的文档片段"""
    chunk_id: str
    content: str
    source_id: str
    source_type: str
    access_level: str = "public"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)


class KeywordRetriever:
    """
    BM25 关键词召回器

    实现标准 BM25 算法：
    score(q, d) = sum( IDF(t) * (tf(t,d) * (k1+1)) / (tf(t,d) + k1 * (1 - b + b * |d|/avgdl)) )

    参数：
    - k1: 词频饱和参数，默认 1.5
    - b: 文档长度归一化参数，默认 0.75
    """

    def __init__(
        self,
        top_k: int = 20,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.top_k = top_k
        self.k1 = k1
        self.b = b
        self._documents: List[IndexedChunk] = []
        self._doc_count = 0
        self._avg_doc_len = 0.0
        self._df: Dict[str, int] = {}  # document frequency

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        简易分词：按空白与标点切分 + 小写化。

        生产环境应替换为 jieba（中文）/ 自定义 analyzer。
        """
        text = text.lower()
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
        return tokens

    def add_documents(self, documents: List[IndexedChunk]):
        """批量添加文档到索引"""
        for doc in documents:
            if not doc.tokens:
                doc.tokens = self.tokenize(doc.content)
            self._documents.append(doc)

        # 更新统计量
        self._doc_count = len(self._documents)
        total_len = sum(len(d.tokens) for d in self._documents)
        self._avg_doc_len = total_len / self._doc_count if self._doc_count > 0 else 0.0

        # 重建 DF
        self._df.clear()
        for doc in self._documents:
            unique_tokens = set(doc.tokens)
            for token in unique_tokens:
                self._df[token] = self._df.get(token, 0) + 1

    def search(self, query: str, top_k: Optional[int] = None) -> List:
        """
        BM25 检索。

        Returns:
            List[RetrievalChunk] - 从 retriever 模块导入的类型
        """
        from src.rag.retriever import RetrievalChunk

        k = top_k or self.top_k
        query_tokens = self.tokenize(query)

        if not query_tokens or self._doc_count == 0:
            return []

        scores = []
        for doc in self._documents:
            score = self._bm25_score(query_tokens, doc)
            if score > 0:
                scores.append((score, doc))

        scores.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, doc in scores[:k]:
            results.append(RetrievalChunk(
                chunk_id=doc.chunk_id,
                content=doc.content,
                score=score,
                source_id=doc.source_id,
                source_type=doc.source_type,
                access_level=doc.access_level,
                metadata=doc.metadata,
                retrieval_source="keyword",
            ))

        return results

    def _bm25_score(self, query_tokens: List[str], doc: IndexedChunk) -> float:
        """计算单个文档的 BM25 分数"""
        doc_len = len(doc.tokens)
        tf_map = Counter(doc.tokens)
        score = 0.0

        for token in query_tokens:
            if token not in tf_map:
                continue

            tf = tf_map[token]
            df = self._df.get(token, 0)

            # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            idf = math.log((self._doc_count - df + 0.5) / (df + 0.5) + 1.0)

            # BM25 TF normalization
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_len)

            score += idf * numerator / denominator

        return score
