import torch
import torch.nn as nn
from transformers import BertModel
from utils import SarcasmDataset, prepare_bert_data

class SarcasmDetector(nn.Module):
    def __init__(self, dropout_rate=0.3, freeze_bert=True):
        super(SarcasmDetector, self).__init__()
        
        # BERT layer with frozen parameters
        self.bert = BertModel.from_pretrained('bert-base-uncased')
        if freeze_bert:
            for param in self.bert.parameters():
                param.requires_grad = False
        self.bert_dim = 768
        
        # Architecture parameters
        self.cnn_out_channels = 256
        self.lstm_hidden_size = 128
        self.dense_hidden_size = 64
        
        # CNN layer
        self.conv1d = nn.Conv1d(
            in_channels=self.bert_dim,
            out_channels=self.cnn_out_channels,
            kernel_size=3,
            padding=1
        )
        
        # BiLSTM layer
        self.lstm = nn.LSTM(
            input_size=self.cnn_out_channels,
            hidden_size=self.lstm_hidden_size,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
            dropout=dropout_rate
        )
        
        # Dense layers
        self.dense1 = nn.Linear(self.lstm_hidden_size * 2, self.dense_hidden_size)
        self.dense2 = nn.Linear(self.dense_hidden_size, 2)
        
        # Regularization and activation layers
        self.dropout = nn.Dropout(dropout_rate)
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax(dim=1)

    def forward(self, input_ids, attention_mask):
        # BERT embedding layer (frozen)
        with torch.no_grad():
            bert_output = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        bert_embeddings = bert_output.last_hidden_state
        
        # CNN feature extraction
        cnn_in = bert_embeddings.permute(0, 2, 1)
        cnn_out = self.relu(self.conv1d(cnn_in))
        lstm_in = cnn_out.permute(0, 2, 1)
        
        # BiLSTM sequence learning
        lstm_out, _ = self.lstm(lstm_in)
        final_hidden = lstm_out[:, -1, :]
        
        # Classification layers
        x = self.dense1(final_hidden)
        x = self.relu(x)
        x = self.dropout(x)
        logits = self.dense2(x)
        predictions = self.softmax(logits)
        
        return predictions

def train_epoch(model, train_loader, optimizer, criterion, device):
    model.train()
    total_loss = 0
    
    for batch in train_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)
        
        # Forward pass
        optimizer.zero_grad()
        outputs = model(input_ids, attention_mask)
        loss = criterion(outputs, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
    
    return total_loss / len(train_loader)

if __name__ == "__main__":
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("Using device:", device)
    
    train_loader, test_loader, tokenizer = prepare_bert_data(
        'data/Mishra/train.txt',
        'data/Mishra/test.txt',
        batch_size=16
    )
    
    model_params = {
        'dropout_rate': 0.3,
        'freeze_bert': True
    }
    
    training_params = {
        'learning_rate': 2e-5,
        'num_epochs': 5,
        'batch_size': 16
    }

    model = SarcasmDetector(**model_params).to(device)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=training_params['learning_rate'])
    criterion = nn.CrossEntropyLoss()
    
    print("Training model...")
    for epoch in range(training_params['num_epochs']):
        loss = train_epoch(model, train_loader, optimizer, criterion, device)
        print(f'Epoch {epoch+1}/{training_params["num_epochs"]}, Loss: {loss:.4f}')