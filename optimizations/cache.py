"""
Sistema de cache em memória com TTL (Time To Live) para melhorar performance.
Reduz queries ao banco de dados para endpoints frequentemente acessados.
"""
from typing import Optional, Any, Dict
import time
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Cache simples com TTL (Time To Live) usando LRU (Least Recently Used).
    
    Ideal para cachear resultados de queries que mudam pouco,
    como listagens de pedidos por status.
    """
    
    def __init__(self, maxsize: int = 256, ttl: int = 30):
        """
        Args:
            maxsize: Número máximo de itens no cache (LRU)
            ttl: Tempo de vida em segundos (default: 30s)
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtém valor do cache se existir e não estiver expirado.
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor cacheado ou None se não existir/expirado
        """
        if key not in self.cache:
            self.misses += 1
            return None
        
        # Verificar se expirou
        if time.time() - self.timestamps[key] > self.ttl:
            del self.cache[key]
            del self.timestamps[key]
            self.misses += 1
            return None
        
        # Mover para o final (LRU - mais recentemente usado)
        self.cache.move_to_end(key)
        self.hits += 1
        return self.cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """
        Armazena valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a ser cacheado
        """
        if key in self.cache:
            # Atualizar valor existente
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.maxsize:
            # Remover o mais antigo (LRU)
            oldest = next(iter(self.cache))
            del self.cache[oldest]
            del self.timestamps[oldest]
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def invalidate(self, pattern: Optional[str] = None) -> None:
        """
        Invalida cache (remove itens).
        
        Args:
            pattern: Padrão para invalidar (ex: "pedidos:status:*")
                     Se None, invalida tudo
        """
        if pattern is None:
            self.cache.clear()
            self.timestamps.clear()
            logger.info("Cache invalidado completamente")
        else:
            keys_to_remove = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.cache[key]
                del self.timestamps[key]
            logger.info(f"Cache invalidado: {len(keys_to_remove)} itens removidos (padrão: {pattern})")
    
    def clear(self) -> None:
        """Limpa todo o cache."""
        self.cache.clear()
        self.timestamps.clear()
        self.hits = 0
        self.misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do cache.
        
        Returns:
            Dict com hits, misses, hit_rate, size
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "ttl": self.ttl,
        }


# Cache global - pode ser ajustado via variáveis de ambiente
import os
CACHE_MAXSIZE = int(os.getenv("CACHE_MAXSIZE", "256"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))  # 30 segundos

cache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

