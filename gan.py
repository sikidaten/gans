import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from torchvision import datasets, transforms
from torchvision.utils import save_image

import argparse
import matplotlib as mpl

mpl.use('Agg')
import matplotlib.pyplot as plt

if not os.path.exists('output'):
    os.mkdir('output')
parse = argparse.ArgumentParser('My gan trainnig')
parse.add_argument('--batchsize', type=int, default=128)
parse.add_argument('--epoch', type=int, default=50)
parse.add_argument('--nocuda', action='store_false', default=True)
parse.add_argument('--k', type=int, default=5)
parse.add_argument('--lrg', type=float, default=0.001)
parse.add_argument('--lrd', type=float, default=0.0001)
parse.add_argument('--maxstep',type=int,default=100000)
args = parse.parse_args()
lzsize = 1
nz = 100
ngf = 64
ndf = 64
nc = 1
zshape = (args.batchsize, nz, lzsize, lzsize)
imagesize = 64
xshape = (args.batchsize, nc, imagesize, imagesize)


class Dloss(nn.Module):
    def __init__(self):
        super(Dloss, self).__init__()

    def forward(self, x, z):
        x = x.view(-1, 1)
        return -torch.mean(torch.log(x) + torch.log(1 - z))


class GLoss(nn.Module):
    def __init__(self):
        super(GLoss, self).__init__()

    def forward(self, x):
        x = x.view(-1, 1)
        return -torch.mean(torch.log(x))

    # network generator


class Generator(nn.Module):
    def __init__(self):
        super(Generator, self).__init__()
        self.main = nn.Sequential(
            # input is Z, going into a convolution
            nn.ConvTranspose2d(nz, ngf * 8, 4, 1, 0, bias=False),
            nn.BatchNorm2d(ngf * 8),
            nn.ReLU(True),
            # state size. (ngf*8) x 4 x 4
            nn.ConvTranspose2d(ngf * 8, ngf * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf * 4),
            nn.ReLU(True),
            # state size. (ngf*4) x 8 x 8
            nn.ConvTranspose2d(ngf * 4, ngf * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf * 2),
            nn.ReLU(True),
            # state size. (ngf*2) x 16 x 16
            nn.ConvTranspose2d(ngf * 2, ngf, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf),
            nn.ReLU(True),
            # state size. (ngf) x 32 x 32
            nn.ConvTranspose2d(ngf, nc, 4, 2, 1, bias=False),
            nn.Tanh()
            # state size. (nc) x 64 x 64
        )

    def forward(self, x):
        x = self.main(x)
        return x


# network of discriminator
class Discriminator(nn.Module):
    def __init__(self):
        super(Discriminator, self).__init__()
        self.main = nn.Sequential(
            # input is (nc) x 64 x 64
            nn.Conv2d(nc, ndf, 4, 2, 1, bias=False),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf) x 32 x 32
            nn.Conv2d(ndf, ndf * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ndf * 2),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*2) x 16 x 16
            nn.Conv2d(ndf * 2, ndf * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ndf * 4),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*4) x 8 x 8
            nn.Conv2d(ndf * 4, ndf * 8, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ndf * 8),
            nn.LeakyReLU(0.2, inplace=True),
            # state size. (ndf*8) x 4 x 4
            nn.Conv2d(ndf * 8, 1, 4, 1, 0, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.main(x)
        return x


def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        m.weight.data.normal_(0.0, 0.02)
    elif classname.find('BatchNorm') != -1:
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.fill_(0)


def main():
    device = 'cuda' if torch.cuda.is_available() and args.nocuda else 'cpu'
    # load data
    train_loader = torch.utils.data.DataLoader(
        datasets.MNIST('../data', train=True, download=True,
                       transform=transforms.Compose([
                           transforms.Resize(imagesize),
                           transforms.ToTensor(),
                           transforms.Normalize((0.5,), (0.5,))
                       ])),
        batch_size=args.batchsize, shuffle=True)

    generator = Generator().to(device)
    discriminator = Discriminator().to(device)
    criterion_D = Dloss()
    criterion_G = GLoss()
    optimizer_g = optim.Adam(generator.parameters(), lr=0.0002, betas=(0.5, 0.999))
    optimizer_d = optim.Adam(discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999))
    # train
    # for epoch
    lossglist = []
    lossdlist = []
    tlist = []
    flist = []
    tflist = []
    tmark = 0.8
    tfgmark = 0.8
    s = 0
    s0=0
    loss_D=torch.tensor(0)
    for e in range(args.epoch):
        count = 0
        # sample train data x

        for i, (x, label) in enumerate(train_loader, 0):
            x = x.to(device)
            tfg = 0
            t = 0
            while tfg < tfgmark:
                s += 1
                # update generator
                generator.zero_grad()
                z = torch.rand(args.batchsize, nz, 1, 1).to(device)
                loss_G = criterion_G(discriminator(generator(z)))
                loss_G.backward()
                optimizer_g.step()
                z = torch.rand(args.batchsize, nz, 1, 1).to(device)
                tfg = torch.mean(discriminator(generator(z))).item()
                print("lossG:%4f tf:%4f" % (loss_G.item(), tfg))
                lossglist.append(loss_G.item())
                lossdlist.append(loss_D.item())

            # update discriminator by sgd
            # sample noise minibatch z
            while t < tmark:
                s += 1
                discriminator.zero_grad()
                z = torch.rand(zshape).to(device)
                loss_D = criterion_D(discriminator(x), discriminator(generator(z)))
                loss_D.backward()
                optimizer_d.step()
                t = torch.mean(discriminator(x.to(device))).item()
                print("lossD:%4f t:%4f" % (loss_D.item(), t))
                lossglist.append(loss_G.item())
                lossdlist.append(loss_D.item())

            print("e:%d s:%d | %d loss_D:%4f loss_G:%4f" % (
                e, s, len(train_loader.dataset.train_data) / args.batchsize, loss_D, loss_G))
            t = torch.mean(discriminator(x.to(device))).item()
            tlist.append(t)
            f = torch.mean(discriminator(torch.rand(xshape).to(device))).item()
            flist.append(f)
            tf = torch.mean(discriminator(generator(z))).item()
            tflist.append(tf)
            # test
            print("t:%4f f:%4f tf%4f->%4f" % (t, f, tfg, tf))

            if s-s0>100:
                save_image((generator(torch.rand(1, nz, lzsize, lzsize).to(device))),'output/' + str(s) + '.png')
                s0=s
            #stop if nan mearge
            if loss_G != loss_G: break
            #stop if over maxstep
            if args.maxstep<s:break
    fig = plt.figure()
    ax1 = fig.add_subplot(211)
    ax1.plot(range(len(tlist)), tlist, label='t')
    ax1.plot(range(len(flist)), flist, label='f')
    ax1.plot(range(len(tflist)), tflist, label='tf')
    ax2 = fig.add_subplot(211)
    ax2.plot(range(len(lossdlist)), lossdlist, label='Loss_D')
    ax2.plot(range(len(lossglist)), lossglist, label='Loss_G')

    plt.xlabel('step')
    plt.ylabel('Loss')
    plt.legend()
    import datetime
    plt.savefig(str(datetime.datetime.now()) + '-loss.png')


if __name__ == '__main__':
    main()
