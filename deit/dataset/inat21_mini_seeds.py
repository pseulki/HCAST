from typing import Optional, Callable, Any, Tuple, List, Union
import os
import torch
from torch.utils.data import DataLoader, Dataset
from timm.data.constants import IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD
from PIL import Image
import numpy as np
import random
import json
import cv2

class iNat21MiniDataset(Dataset):
    def __init__(self, 
                 root, 
                 is_train: bool = True,
                 transform=None,
                 is_hier: bool = True,
                 category: str = 'name',
                 path_yn: bool = False,
                 mean: Union[List, Tuple] = IMAGENET_DEFAULT_MEAN,
                 std: Union[List, Tuple] = IMAGENET_DEFAULT_STD,
                 n_segments: int = 256,
                 compactness: float = 10.0,
                 blur_ops: Optional[Callable] = None,
                 scale_factor=1.0,):
        self.mean = mean
        self.std = std
        self.n_segments = n_segments
        self.compactness = compactness
        self.blur_ops = blur_ops
        self.scale_factor = scale_factor
        self.is_hier = is_hier
        self.path_yn = path_yn
        self.category = category
        self.transform = transform

        self.img_path = []
        
        self.species_label_list = []
        self.family_label_list = []
        self.order_label_list = []

        if is_train:
            filename = 'data/inat21_mini_train.txt'
        else:
            filename = 'data/inat21_mini_val.txt'

        with open(filename) as f:
            for line in f:
                self.img_path.append(os.path.join(root, line.split()[0]))
                id = int(line.split()[1])
                family_id = int(line.split()[2])
                order_id = int(line.split()[3])
                self.species_label_list.append(id)
                self.family_label_list.append(family_id)
                self.order_label_list.append(order_id)


        self.targets = self.species_label_list  # Sampler needs to use targets

    def __len__(self):
        return len(self.species_label_list)

    def __getitem__(self, index):

        path = self.img_path[index]
        #label = torch.tensor([self.super_label_list[index], self.order_label_list[index], self.class_label_list[index]])

        with open(path, 'rb') as f:
            sample = Image.open(f).convert('RGB')

        if self.transform is not None:
            sample = self.transform(sample)

        # Prepare arguments when multi-view pipeline is adopted.
        compactness = self.compactness
        blur_ops = self.blur_ops
        n_segments = self.n_segments
        scale_factor = self.scale_factor
        if isinstance(sample, (list, tuple)):
            if not isinstance(compactness, (list, tuple)):
                compactness = [compactness] * len(sample)

            if not isinstance(n_segments, (list, tuple)):
                n_segments = [n_segments] * len(sample)

            if not isinstance(blur_ops, (list, tuple)):
                blur_ops = [blur_ops] * len(sample)

            if not isinstance(scale_factor, (list, tuple)):
                scale_factor = [scale_factor] * len(sample)


        # Generate superpixels.
        if isinstance(sample, (list, tuple)):
            segments = []
            for samp, comp, n_seg, blur_op, scale in zip(sample, compactness, n_segments, blur_ops, scale_factor):
                if blur_op is not None:
                    samp = blur_op(samp)
                samp = (samp.data.numpy().transpose(1, 2, 0) * self.std + self.mean)
                samp = (samp * 255).astype(np.uint8)
                samp = cv2.cvtColor(samp, cv2.COLOR_RGB2LAB)
                seeds = cv2.ximgproc.createSuperpixelSEEDS(
                    samp.shape[1], samp.shape[0], 3, num_superpixels=self.n_segments, num_levels=1, prior=2,
                    histogram_bins=5, double_step=False);
                seeds.iterate(samp, num_iterations=15);
                segment = seeds.getLabels()
                segment = torch.LongTensor(segment)
                segments.append(segment)
        else:
            if blur_ops is not None:
                samp = blur_ops(sample)
            else:
              samp = sample
            samp = (samp.data.numpy().transpose(1, 2, 0) * self.std + self.mean)
            samp = (samp * 255).astype(np.uint8)
            samp = cv2.cvtColor(samp, cv2.COLOR_RGB2LAB)
            seeds = cv2.ximgproc.createSuperpixelSEEDS(
                samp.shape[1], samp.shape[0], 3, num_superpixels=self.n_segments, num_levels=1, prior=2,
                histogram_bins=5, double_step=False);
            seeds.iterate(samp, num_iterations=15);
            segments = seeds.getLabels()
            segments = torch.LongTensor(segments)

        if self.is_hier:
            if self.path_yn:
                return sample, segments, self.species_label_list[index], self.family_label_list[index], self.order_label_list[index], path
            return sample, segments, self.species_label_list[index], self.family_label_list[index], self.order_label_list[index]
        else:
            if self.category == 'name':
                return sample, segments, self.species_label_list[index]    
            elif self.category == 'family':
                return sample, segments, self.family_label_list[index]
            elif self.category == 'order':
                return sample, segments, self.order_label_list[index]
