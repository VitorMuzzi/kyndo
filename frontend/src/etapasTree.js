// Lógica pura da organização de etapas. Fica fora do componente pra poder ser
// testada sem React — é tudo aritmética de índice, o tipo de coisa que não se
// confere no olho.
//
// O card guarda exatamente 2 níveis (etapa -> subetapas). Aqui a lista é
// ACHATADA, com um `nivel` (0 ou 1) por linha, porque assim arrastar, mover e
// indentar viram operações simples de array. A árvore é remontada na saída.

export const achatar = (checklist) => {
  const linhas = [];
  for (const item of checklist || []) {
    const { subetapas, ...resto } = item;
    linhas.push({ ...resto, nivel: 0 });
    for (const sub of subetapas || []) {
      linhas.push({ ...sub, nivel: 1 });
    }
  }
  return linhas;
};

export const montarArvore = (linhas) => {
  const arvore = [];
  for (const linha of linhas) {
    const { nivel, ...resto } = linha;
    // Linha de nível 1 sem nenhum pai acima não pode existir — promove.
    if (nivel === 0 || arvore.length === 0) {
      arvore.push({ ...resto, subetapas: [] });
    } else {
      arvore[arvore.length - 1].subetapas.push(resto);
    }
  }
  return arvore;
};

// Quantas linhas o bloco que começa em `i` ocupa: a linha mais as filhas dela,
// quando é etapa de nível 0. Arrastar um pai leva as filhas junto.
export const tamanhoDoBloco = (linhas, i) => {
  if (linhas[i]?.nivel !== 0) return 1;
  let n = 1;
  while (i + n < linhas.length && linhas[i + n].nivel === 1) n++;
  return n;
};

export const moverBloco = (linhas, de, para) => {
  const tam = tamanhoDoBloco(linhas, de);
  const bloco = linhas.slice(de, de + tam);
  const resto = [...linhas.slice(0, de), ...linhas.slice(de + tam)];
  // `para` é índice na lista ORIGINAL; quando o bloco saiu de antes dele, os
  // índices à direita andaram `tam` casas pra trás.
  const destino = para > de ? para - tam + 1 : para;
  resto.splice(Math.max(0, Math.min(destino, resto.length)), 0, ...bloco);
  return resto;
};

export const podeIndentar = (linhas, i) =>
  i > 0 && linhas[i].nivel === 0 && linhas.slice(0, i).some(l => l.nivel === 0);

export const podeDesindentar = (linhas, i) => linhas[i]?.nivel === 1;

// Indentar leva as filhas junto, achatadas no mesmo nível (só há 2 níveis).
// `notas` é descartada de propósito: sub-etapa não guarda observação, e o
// componente avisa antes de chamar isso.
export const indentar = (linhas, i) => {
  const tam = tamanhoDoBloco(linhas, i);
  return linhas.map((l, idx) => {
    if (idx === i) {
      const semNotas = { ...l, nivel: 1 };
      delete semNotas.notas;
      return semNotas;
    }
    if (idx > i && idx < i + tam) return { ...l, nivel: 1 };
    return l;
  });
};

export const desindentar = (linhas, i) =>
  linhas.map((l, idx) => idx === i ? { ...l, nivel: 0 } : l);

export const moverParaCima = (linhas, i) => {
  if (i === 0) return linhas;
  // Um bloco de nível 0 pula o bloco anterior inteiro; uma sub-etapa anda 1.
  if (linhas[i].nivel === 1) return moverBloco(linhas, i, i - 1);
  let inicioAnterior = i - 1;
  while (inicioAnterior > 0 && linhas[inicioAnterior].nivel === 1) inicioAnterior--;
  return moverBloco(linhas, i, inicioAnterior);
};

export const moverParaBaixo = (linhas, i) => {
  const tam = tamanhoDoBloco(linhas, i);
  const proximo = i + tam;
  if (proximo >= linhas.length) return linhas;
  const tamProximo = tamanhoDoBloco(linhas, proximo);
  return moverBloco(linhas, i, proximo + tamProximo - 1);
};

export const removerBloco = (linhas, i) => {
  const tam = tamanhoDoBloco(linhas, i);
  return [...linhas.slice(0, i), ...linhas.slice(i + tam)];
};
