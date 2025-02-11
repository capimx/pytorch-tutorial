import torch
import gensim
import numpy as np
import torch.nn as nn
import torchvision.models as models
from bert_embedding import BertEmbedding
from torch.nn.utils.rnn import pack_padded_sequence

class EncoderCNN(nn.Module):
    def __init__(self, embed_size):
        """Load the pretrained ResNet-152 and replace top fc layer."""
        super(EncoderCNN, self).__init__()
        resnet = models.resnet152(pretrained=True)
        modules = list(resnet.children())[:-1]      # delete the last fc layer.
        self.resnet = nn.Sequential(*modules)
        self.linear = nn.Linear(resnet.fc.in_features, embed_size)
        self.bn = nn.BatchNorm1d(embed_size, momentum=0.01)
        
    def forward(self, images):
        """Extract feature vectors from input images."""
        with torch.no_grad():
            features = self.resnet(images)
        features = features.reshape(features.size(0), -1)
        features = self.bn(self.linear(features))
        return features


class DecoderRNN(nn.Module):
    def __init__(self, embed_size, hidden_size, vocab, num_layers, max_seq_length=20):
        """Set the hyper-parameters and build the layers."""
        super(DecoderRNN, self).__init__()
        Bert_file = "bert-base-uncased.30522.768d.vec"
        print("M1")
        Lookup = gensim.models.KeyedVectors.load_word2vec_format(Bert_file, binary=False)
        bert_embedding = BertEmbedding()
        Embed = np.zeros((len(vocab), embed_size))
        print("M2")
        Embed[vocab('<pad>'),:] = np.random.normal(0, 1, embed_size)
        Embed[vocab('<start>'),:] = np.random.normal(0, 1, embed_size)
        Embed[vocab('<end>'),:] = np.random.normal(0, 1, embed_size)
        Embed[vocab('<unk>'),:] = np.random.normal(0, 1, embed_size)
        print("M3")
        for word in vocab.__keys__()[4:]:
            try:
                Embed[vocab(word),:] = Lookup[word]
            except:
                bert_word = word
                token = bert_word.split('\n')                
                pred = bert_embedding(token)
                Embed[vocab(word),:] = pred[0][1][0]
        
        print("M4")
        self.embed = nn.Embedding(len(vocab), embed_size)
        self.embed.weight.data.copy_(torch.FloatTensor(Embed))
        self.lstm = nn.LSTM(embed_size, hidden_size, num_layers, batch_first=True)
        self.linear = nn.Linear(hidden_size, len(vocab))
        self.max_seg_length = max_seq_length
        
    def forward(self, features, captions, lengths):
        """Decode image feature vectors and generates captions."""
        embeddings = self.embed(captions)
        embeddings = torch.cat((features.unsqueeze(1), embeddings), 1)
        packed = pack_padded_sequence(embeddings, lengths, batch_first=True) 
        hiddens, _ = self.lstm(packed)
        outputs = self.linear(hiddens[0])
        return outputs
    
    def sample(self, features, states=None):
        """Generate captions for given image features using greedy search."""
        sampled_ids = []
        inputs = features.unsqueeze(1)
        for i in range(self.max_seg_length):
            hiddens, states = self.lstm(inputs, states)          # hiddens: (batch_size, 1, hidden_size)
            outputs = self.linear(hiddens.squeeze(1))            # outputs:  (batch_size, len(vocab))
            _, predicted = outputs.max(1)                        # predicted: (batch_size)
            sampled_ids.append(predicted)
            inputs = self.embed(predicted)                       # inputs: (batch_size, embed_size)
            inputs = inputs.unsqueeze(1)                         # inputs: (batch_size, 1, embed_size)
        sampled_ids = torch.stack(sampled_ids, 1)                # sampled_ids: (batch_size, max_seq_length)
        return sampled_ids
