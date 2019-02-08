from typing import Dict, Optional, List

import torch
from overrides import overrides
from allennlp.common import Registrable
from allennlp.modules import FeedForward, Seq2SeqEncoder, Seq2VecEncoder
from allennlp.nn.util import (get_final_encoder_states, get_text_field_mask,
                              masked_max, masked_mean)
from allennlp.common.checks import ConfigurationError

class Encoder(Registrable, torch.nn.Module):

    default_implementation = 'feedforward'

    def __init__(self, architecture: torch.nn.Module) -> None:
        super(Encoder, self).__init__()
        self._architecture = architecture

    def get_output_dim(self):
        return self._architecture.get_output_dim()

    def forward(self, *args):
        raise NotImplementedError

@Encoder.register("feedforward")
class FeedForward(Encoder):

    def __init__(self, architecture: FeedForward) -> None:
        super(FeedForward, self).__init__(architecture)
        self._architecture = architecture

    @overrides
    def forward(self, embedded_text) -> torch.FloatTensor:
        return self._architecture(embedded_text)

@Encoder.register("seq2vec")
class Seq2Vec(Encoder):

    def __init__(self, architecture: Seq2VecEncoder) -> None:
        super(Seq2Vec, self).__init__(architecture)
        self._architecture = architecture

    @overrides
    def forward(self, embedded_text, mask) -> torch.FloatTensor:
        return self._architecture(embedded_text, mask)

@Encoder.register("seq2seq")
class Seq2Seq(Encoder):

    def __init__(self, architecture: Seq2SeqEncoder, aggregations: str) -> None:
        super(Seq2Seq, self).__init__(architecture)
        self._architecture = architecture
        self._aggregations = aggregations.split(",")

    @overrides
    def get_output_dim(self):
        return self._architecture.get_output_dim() * len(self._aggregations)

    @overrides
    def forward(self, embedded_text, mask) -> torch.FloatTensor:
        encoded_output = self._architecture(embedded_text, mask)
        encoded_repr = []
        for aggregation in self._aggregations:
            if aggregation == "meanpool":
                broadcast_mask = mask.unsqueeze(-1).float()
                context_vectors = encoded_output * broadcast_mask
                encoded_text = masked_mean(context_vectors,
                                           broadcast_mask,
                                           dim=1,
                                           keepdim=False)
            elif aggregation == 'maxpool':
                broadcast_mask = mask.unsqueeze(-1).float()
                context_vectors = encoded_output * broadcast_mask
                encoded_text = masked_max(context_vectors,
                                          broadcast_mask,
                                          dim=1)
            elif aggregation == 'final_state':
                is_bi = self._architecture.is_bidirectional()
                encoded_text = get_final_encoder_states(encoded_output,
                                                        mask,
                                                        is_bi)
            else:
                raise ConfigurationError(f"{aggregation} aggregation not available.")
            encoded_repr.append(encoded_text)

        encoded_repr = torch.cat(encoded_repr, 1)
        return encoded_repr
