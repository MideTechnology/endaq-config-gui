from wx.lib.embeddedimage import PyEmbeddedImage

icon = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAyeAAAMngHscVUT'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAEJVJREFUeJzVm3l0FFW+'
    b'xz/VnU66k3Q6JOmQxEBC2FEYIYIMyICgiSKoID4EnHFEBsQAcUAdDAoyEYfRQQkQB/HIO288'
    b'4wZzHCBs6pMtIMugYAiENWEJIUEgSyekq6q73h+VCp30HuKZed9z6vRSd/v86tbv3vrdW/D/'
    b'SwKQBfwLsAE/Ak//W1vkQQKQDvS4zXImA58Cc4FOgAnYZI4wKc8OT1SWjEtQfvurRCXcFKYA'
    b'a5rq/bcqHngZKAEUwAG81May5jSVoR1O4EayNUr5dKpVUZbSfOQ9lahERZjabAR9GxvYWpnA'
    b'PuARvV4fZzab0el0gizLGU117AiirGlAvslkElJTU1EUBVmWhcTYCOOKcaE82e2nFonvTbAR'
    b'brHyXZkz3S5KSUBBMA1vLwP8BegXHR3NhAkTWLhwIeXl5VRVVSFJ0nAgGvgqgHKmAGuNRqOu'
    b'b9++fPjhhxw9ehSp/horxoUyPu2ax0yDE2yYouI0I3RCNYISSMPbywAvCoKQnJ2dzYwZM7BY'
    b'LGRkZHD58mUuXryIKIqDgTuALT4aNh74e2hoqL5Hjx6sXLmS+fPnc67kiE94TS5G6G8XpWQC'
    b'NEJ7GeDlsLCwuMzMTHr0UH2fIAgMHz6cxsZGTp48iSiKA4CuwJce8g8DNhoMBkNqaipr1qwh'
    b'JycnYHhNLkYYEKgR2ssAr5tMpohHHnmElJSUFicGDRrkaoR+QBFwolX+zwVBSElJSWHt2rUs'
    b'WLAgaHhNwRpBF1Tp3hUdEhKC2Wz2eDIrK4v09HQEQQD4Paq37tB03AMMjoqKYvHixbz22mtt'
    b'hteUfXcFi8dYsESGP4c6OnjlbA8DRAKhgiAQFRXlNdHUqVOxWCwAQ1GHtetNxyEAnU7HmjVr'
    b'OHviFrxTEfi6PJ5dFXEoAbm0WwrUCCHBFetR0doXXwbo3bs3kiQRFRVFSIharcPhICQkBFmW'
    b'kSSpBXyDrGfOri4UFNnQCTrG9+/Ke/eVYtA5A25Y9t0VQCKLCniuxtYAMB3V+M1qDwPUALLT'
    b'6QwpLS0lLi7OY6KwsDA++ugjlKZLGRkZiU6nQ5Zlli5dyvnTx1gxLpQnul7jpkPPrJ1d2HSk'
    b'BlBwAF8cqsUup5E/4hyh7WiE9nCCIjDcbrenVVVVMXbsWK8JrVZr82GxWDAajSxatIjSkz+2'
    b'gM/acQveVSev2DlrT+ShlGr0QuD3hC/H2F6jwH1A+vXr17nzzjvp1KmT3wyiKDJ37tzmbu8P'
    b'XlN7G8GTAaKBF4GHUT30nUAakAzEoRqtpimtHlgFPG8ymejTpw/Tpk1rvse9yW63k52dHdCV'
    b'N4SG8Ztnp/ObZ6YiO+Hc2VPtZYQEoMDTw8NXwIN+ytoD/AmYATwWGRnJiBEjyM3NRafzPbBo'
    b'8BfOFLPi8VDGd/3JJ/zMrGxez3kZgIabN8maPZeCDf9AEOCx/pagfQJA3pFEcjZcp+GmfUrr'
    b'HvAwsNBsNtOrVy/MZjNhYWEYDAZCQ0MJDQ3FZDJht9tTUOftvcxmM1OmTGH+/PnaOP+zwAMY'
    b'DAYyHhzFmXMXOVVy4rZ6wumGeI6et/Vw7at64M+CINCnTx/WrFnjMXNxcTFLlizh3LlzhISE'
    b'8Morr/Doo4/6rdQb/AvfplFwtNoD/Iu8nuP+NB1uMpG/8l0ACjb8gw0/1ADBjw7dYxWAFNce'
    b'8ADwUlRUFMuXLyc6Otpjxvj4eMaNG0dNTQ3Tpk1j1KhRPwN8yyvfWu3RE9b+aOboeduPrgZI'
    b'BKYaDAa6detGz549vWYWBIEhQ4aQnJzst6L2hm9OextG+PyUlbe/rkGU5CWuBrgIdBNFsd/3'
    b'33/P/fff77UXBCoNvvUkxxO8IOiYPnMOb7z+h4DLNxgMZDwwiqLjpwIeHTaXxfDiRpmrN+o3'
    b'A/NaO8FvgCdFUYzZt28fEyZMQK9v21RBFEXmzZvXYqhrkPXM3JnG5lbwAPEJd/DRh3/FGBYW'
    b'VD0Gg4GGRpGvtm0B1HnCJUcCo1NuuKXdXBbDC186uFBZsxsYB4itx6w6YJKiKGJlZSVLly4N'
    b'qjGaPE1yNPgtR9zhAa79VMmWrV+3qb5jxcXN3xVF4csfGthzpeWUvBX8aKAePM8ELwMNsixn'
    b'Xrx4kZSUFNLS0gJujHbl3eB3pLHFw5VvbrjTyfc/HCG5Uyo9e3QLuL63l63gww/ycTjkW3/q'
    b'dDzWRyHN3AB4hwfvU+H9wEBRFLvv27ePoqIirFYrCQkJPsd6Df7M8R+CgtdUb6vlwMFDARvh'
    b'7WUryHvvHUR7Y4v/x/4iiux+5QiCb3hfBgDYCqSLophWVlbGN998Q2JiYnPIKxB4dZLj+Z73'
    b'pkCN4A3+ob7RrBpRRpje2QQvc6Gy1iM8+A6I3AAygGcURcFgMLiFuzR5g2/t7QVBR5wpEoPe'
    b'4NMIlRWXyMl5lY0F24KG/+vIMiINssuV9w7vzwA0tfwwqM7FkwGCgX/WaOa7KxV8IDtICDO1'
    b'yQjBwXvu9q4KZIwbBkw0mUzMmDGjTfAAMcZw1lZdJkay0/NmPT9ExVDiEH1WXG+r5dC/DhPd'
    b'wUrnzsn8+Z3lvL9qeaDwB1AXbLzCQ2AxwR4AMTExbYYHqJVFdpnViVVNiIFSfWDhyIryC8x9'
    b'cRZDhg4jf8W7bvCZnuFBjXb9CXgEH0tmvh7ch6I+Fk8CWgyFwcIDyLLEa2FGCu5I5bxex4k4'
    b'Gd3T4SCA/u8glTV4bYgsS1RdKXf7P7NvNKtbwf9UJ2mn05uO2cA24HfApUAM0AH4CHWmBKhz'
    b'/z59+rQZXtNVsZFNTd91U8Kp+v0FAKx0giVes3mUJ3hrcjdmP/UUpaWlSJLEgQMHKC0tpa6u'
    b'7iHgGGpI/r99GeCXqEvSKWazmZiYGO6++26MRiPDhg27LXg3uSQVEILJ6RU+Pz8fk+mWc501'
    b'axb79+8nJyeH2tpaiyRJa4EJqIHRcrVurQ3q0vabgiAYzGYzr776KqNHj24uzDt8FwqOeo/h'
    b'eZMhxYRjsqDeAp+ArupOHI40BGUvkujWU4OGd1V9fT25ubkUFhZSV1cHUI26/2CrgBrn+xh4'
    b'yGQykZSUxKpVq0hKSvIAf4R3HwtjYvertwXfWmHh91BZ8RmyZCE6djthIdNwOBrd0rUF3lWF'
    b'hYUsXLiQmpoaZFk+A3TXo67YPhAZGcmYMWPIy8vTVnDaBJ/SpTvjJ0zkvyZOZuyjj5M+8F4i'
    b'zRbKL11EliQ8SdANpbb6CQBkOZ4oy2c45Lp2hQfo3LkzHTp0oLCwEIfDcQNYEQLcEx4eTlZW'
    b'FpMnT26RQZKkoODvf+BhFi9aQGJCxxb///bXk9i05SveXfYOly6UubdMKaRD7GZsdUOxdlyB'
    b'2HjFJ3xWG+A1lZSUYLfbAU6C6gSPNzY2Drx586Yb/Ny5cwOGTx80lHeWvonF4nl5bOzoDAQB'
    b'cua/ws2GlnMTWawg1PA7rPGxSI1VKMqt2J4n+LjkbqxatSpo+NOnT7N//37t50lQJ0KHnU4n'
    b'Bw8ebDO8oNMxadJTXuE1jXk4gxEjMzyec8gSYuOVgOHDw8Pdyjhw4ADXr19v/m2329m7dy8L'
    b'Fixg5MiRTJ8+nbKyMu30d6D2gIPA88eOHWPkyJH07duXiooK6q5VNMMrCupCpReH1yWtBw9n'
    b'+A+OAgzo35+tBZ72SLTUQ307sHpkKREBwl+6dIl58+YhCAIRERGEh4dz9epVFEXRPL+mY8Df'
    b'gPWaAdYDL9hstntsNhs7d+4kKS6qGR5g1xUrBUX1HuEBYuOshIb6fsLTlJiUiCDoWlzp24UH'
    b'eOutt7DZbCiKQm1treupRmAn6lLYZqDM9WQIahhsENAP+DgpLqqvKzyAUe9EL4CMZ7X2H76k'
    b'NrJ94YuLiykqKtJWnv+AuonSjHqff42PByJtJmgA3vQEDzA4/hpP9O/KpwfrPDb+3JmTnDh5'
    b'ht49/UdxTp065fVcW+ABcnNztau+B3jbbyNcpEOdBX6RFBc1xhO8pmVDS5mQbvEYEmuor+OT'
    b'Tz/3W9mVyqvs+PZbj+fUp7qW8B1TevL+++/7hN+1axfl5eWg3p+v+G1EK+mBGZERxpfyxkcw'
    b'qYdneACdoJDZuZrzUhInKuxu58+ePU1EVAd+0e8uj/lt9fXkvL6Y7w9953bO1dtvOBfLrH86'
    b'SEjpycqVKzEajV7b5HQ6mTlzJteuXQM4Arzuh9dNemDlxHutnRYNqfSb2JcRZEni0MEDXK68'
    b'RqfkTsTGdADUIXXr9v/lraVvU7jrG7cyW8PP2SAHBA/Q2NjIzp07qa2tRZKkRNQw3oFA4UHt'
    b'/tcWP5YQs/CXV/wm1iQ7dczZ3ZX1h6ubt7y4KsJsIa1rd8LDw/np6lVKz57C6XS4pbsdeE1O'
    b'p5OcnBx27NhBY2OjBPQCzgXKIgCHn74vccDHYyoCzQP4N4I/ucJvLI1l9j+Dh9ckSRKZmZna'
    b'rTAPeDfQvHrgxukq8UljVEeGJNb5zaDJn0/wpcy7olk9qn3gAfR6PWVlZZw4cQLUke1vAecF'
    b'jsuyI67wnDgo1BzP0CRbwBW3xQgZd0Wz+oEyzE3efnaADk8URZ/rlEajkd27d2O325OBPNTN'
    b'W/4Zmj7nNNy0r3yj4DrvHE4MCERTiM7Jil+dZUJ6tN8dIs3wIbeGutg7upKXl+cR3m63s3Hj'
    b'RsaPH8/48eNxONz9iKYBAwZoX0Pxv8WnWa4m3SbJjpi9pdK9P0dP8Aafn5/vNs6XlJTw3nvv'
    b'kZuby+7du6mqqkKWZWRZZuDAgZ5B9Hr27NlDRUUFqLPbTR4Tts7X6vfPYoRA4ffv38/zzz/P'
    b'+vXrOXbsGHa7HUmSbMBRSZLuKCkp4caNG/Tu3dvjo7AWCHU4HAkE6Ag93VS3ZYSMlGoqHAmc'
    b'uuoEQceYflG8f/+te97XlT98+DBbt26loaEB1PF8MTAV+AC4SxTF3iUlJaxbt47jx4+TmppK'
    b'bGwsoA6H69at0yLC4ahrAn43DXm7aQUgL9wUNvuNMTG8nB7cEAmw50ocdoeOkUlX0QlKM3x0'
    b'QiqrV6/2OL0tLi4mKyuLGzdugPp84vr8FYL6AlU2kKRtzu7YsWNzrzly5IhmvOWoIXC/8uW1'
    b'mo2weEwML7XBCJo0+PJr9WzatKlFwNVVRUVFzJo1i+rqagW1d3qaYBiAJ1ENMQjAbDYjiqIW'
    b'6voj8IaXvG7ytT6lANkNN+0rFxVc5y9Bjg6aNPjzlTXO0NDQFpGn1tq+fTs2mw3gNN4BJOAT'
    b'4F7UdYzP6urqJLvdfhN4DljkI6+bAnnNrM09wQV+DyrUVKvVyvbt293GdLvdzoMPPkhNTQ2o'
    b'r9stC7gidXuvE6j1l7C1At0B1ewYw8zxDAnAMbaCH40aessC9FarlV69erVIv379evbu3Yss'
    b'y3XAr4FgppeNQaZvVjBbwAI2ggd4G+oG62RJku45fvw4U6ZMad5XrCgK8+bNo7q6GmA1sKEt'
    b'MG1RsHvgtkmyI25vqTTImxFc4HfgvjmhCHhBURR9fHx8cy/Yt28f27Ztw263O1Gvvvset/8g'
    b'CcCqyAijsmxiYovXWL+YZlU6d7QowLeAtzDOB4BisViUUaNGKYMHD1ZiYmK0V2T9h4v/QyQA'
    b'q8KNYcozv0pU3ny8o/Ls8OZ3eLfiHR4gBbVXKK0OBzD4Z263m273jeungPlAF+AU8D9APv6H'
    b'oaGoq7MhqJ5bRI3e7rzN9gSt/wO8fYmPeDB1vwAAAABJRU5ErkJggg==')

#----------------------------------------------------------------------
info = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA8IAAAPCAEz+ykV'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAATpJREFUOI2lk7EuBFEU'
    b'hr8zSNwz2aAUiQIh0YpCpaIQnRdQeQReYEuteAeJRCFRU4hKZyMhEQ3JNousGZHl10wmY3ZY'
    b'Gye5zfnP/517Tu6Ff4ZVJUPQpBnrZswCHxJXUcRxu23NHjy5u/bd1XGXSid1Vx00+JM5uOu8'
    b'YHis1TTnrkV3tQv5I9BAl91de8WOcazTDGzuuilpO992EIImzLgDhkrcQ6AGrJbyT0nCONhb'
    b'BGDGWoW5CYwAEfBS0kbjmGUyEYmpiqWcJYmtJImtANddGxMzOcCMTgWgV7wXb3DVr1uikQOG'
    b'hzmhe87f4j5NucgBrZY9m1Hvo/s22AdA/qpeX9l1Zx7YzIrG3LWQyXHBX09TO/iR7q4tdz1U'
    b'POXbELRRrq/8TKCBEFiKIqaBT4lGknAJpr+O+ef4AlD2jNWOAREZAAAAAElFTkSuQmCC')

#----------------------------------------------------------------------
warn = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA8IAAAPCAEz+ykV'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAOBJREFUOI21kbFKA0EU'
    b'Rc8GUREJAUshhWCZLoWFTYr4B+nT+w22Cnb6DVZb5E8sA+lSCVYDSVhCiPFY6OKyzJpkwQe3'
    b'u+fMmxn4z1EGynVd+FiZKq9Ko47gTvEnw33h89mMLE0xTXG95l1p7iN4mUwQvjOfo/KwK3yl'
    b'fEYEK+Wy3G+U4AR4ApKI+xB43Hb6MH+4yAZ5bqrgU+VtB8FYOYgJ7gulbbktwxfKsljKMux2'
    b'sd+PCoJyVhSMyqUQsNXCdhs3m6jkOYd7VauGgItF5TU+lE6inABHf35P9Sxrcr/zBYuXHMHz'
    b'mA2VAAAAAElFTkSuQmCC')

#----------------------------------------------------------------------
error = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA8IAAAPCAEz+ykV'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAPVJREFUOI2lkbFKA0EQ'
    b'hr+7eHiIsZFUVgZCmuvSaOkz+AA+g61oaxmwyBMI6eJzWNjaaiXYBAIKwSh+FncbIhdwLw4M'
    b'LDv7f/PPDvwzEmEH2N5QP0c4EaxlnutgUGarVa/Dp1AAIExqD/p9l9FurwPcLH0Ih8K8AWAq'
    b'7AOkAAk8A8MGs18lMP11I+wKLxEOHoWtoEvDIYF34CKi+3kCX2srlmu9FzTLtNstM01D97s/'
    b'8cKR8G2W6Xiso1EQfwi9CIcg3Nrp6GKhs1lwcB0lrgAHwptFUY4Ar8JeNKCCXK78/FkjcQXI'
    b'hSfhwZVtNYWcCscbiWPjBze3yYSzUy07AAAAAElFTkSuQmCC')


#----------------------------------------------------------------------

WIFI_ICONS = (
    # wifi_0 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAJ4SURBVDiNnZS/axRBFMff29md2b29vTMiZyqDlZW1WGkjgoiIoghWWgYsBP8Hi9jZ6x8g'
        b'apPOTrC0jE0gEosouezlbn/c7MzOm2eTDfEMRv3W3/m8N+/7ZhCOETOPAOCWMeah9/48MycA'
        b'AIiogyD4qpR6DwDriLi1eBYXQCvOuZdN01y21p7y3ofHFUREL6WcJknyKQzDJ4i4/QuQmYX3'
        b'/qnW+pnWerRY6A/iOI7zXq+3FgTBC0T0yMwhEb2azWb3vPdx5xRCNEqpMgxDI4RwAABEFDrn'
        b'lDEmI6JDbxAEzXA4fCOEeIxt274ty/ImEckO1O/3d6MoaohIWmuT7upBEDgppRZC2LZt46qq'
        b'Rh1YCGGzLFsPmdkwMwIAJEkySdN0zxiT7u/vnzvaRae6rkEI0aRpure0tPStruszWuvTzIzM'
        b'3CIzR9badefcxV6vV5VledYYM/ibASqlZlmW7c7n8yyKoi9RFN3oQukDwLuiKC5Zawddkkqp'
        b'mZSyCsOwBQBwzkXW2r4xZsjMAQCAlLIYDAafAeA2IhaHaTLzqGmaj1VVXQjDcD4YDH4gom+a'
        b'JiMidTAnE8dxycxBURTLzrlev9/fjOP4CiJ+h8X1YOYVY8wHKSUYY7K6rkddJ50QkdI0HSul'
        b'SmstKqWuH13wRfO2Uupu27ZYVdXyIuygqKiqarltW1RK3T/utfwmZr5aFEWe53mrtd7x3m96'
        b'7ze11jt5nrdFUeTMfO1E0AL0DhFtOOe2yrKclGU5cc5tEdEGMz/4J9gR6Op0Op2Nx2Mej8c8'
        b'nU5nzLz6X7BORPR8MpnM8zzXRLR2kv/ET4CZAyJ6DQAghHiEiP5P/p8z44t3EE1m9AAAAABJ'
        b'RU5ErkJggg=='),

    # wifi_25 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAKFSURBVDiNnZS/axRBFMff29md2b29vTMiZyqDpLjKtGKlcIggIqIogpUWVwQsBP8HC+3s'
        b'9Q8QtUlnJ1jaBHJN4CQGosRs4u2Pm53ZmXk22RDPkKjf+juf9+Z93wzCESKiHgDcVEo9cM6d'
        b'J6IIAAARped5X4QQ7wFgBRHHs2dxBrRgjHlZVdUlrfUp55x/VEFEdJzzn1EUffJ9/zEibvwG'
        b'JCLmnHsipXwqpezNFjpGFIZh2mq1nnue9wIRHRKRb619NZlM7jrnwsbJGKuEELnv+4oxZgAA'
        b'rLW+MUYopRJr7YHX87yq2+2+YYw9wrqu3+Z5fsNayxtQu93eDoKgstZyrXXUXN3zPMM5l4wx'
        b'Xdd1WBRFrwEzxnSSJCs+ESkiQgCAKIp24zjeUUrFe3t75w530agsS2CMVXEc78zNzX0ty/KM'
        b'lPI0ESER1UhEgdZ6xRhzodVqFXmen1VKdf5mgEKISZIk29PpNAmCYBQEwfUmlDYAvMuy7KLW'
        b'utMkKYSYcM4L3/drAABjTKC1biulukTkAQBwzrNOp/MZAG4hYnaQJhH1qqr6WBRF3/f9aafT'
        b'+Y6IrqqqxFor9uekwjDMicjLsmzeGNNqt9vrYRheRsRvMLseRLSglPrAOQelVFKWZa/ppBEi'
        b'2jiOfwghcq01CiGuHV7wWfOGEOJOXddYFMX8LGy/KCuKYr6uaxRC3DvqtfwhIrqSZVmapmkt'
        b'pdxyzq0759allFtpmtZZlqVEdPVE0Az0trV2bTQajYfD4e5wONwdjUZja+0aEd3/J9gh6PJg'
        b'MJgAAAEADQaDCREt/xes0ebm5rN+vz9dXFyU4/H4+Un+Ez8BIvJWV1dfAwAsLS09RER3nP8X'
        b'Y/J4V5QdOdMAAAAASUVORK5CYII='),

    # wifi_50 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAKhSURBVDiNlVQxaxRREJ7Zt/t29+52LyeXOyuDprjKBCuxUjhsREQE4YKVlgEhgv8ghUUs'
        b'AhZJkWgXBFGbFFcLljZXWOTgRAOJCYmX27273ff27RurDecZk/jBdN98M/PNvIdwAoioAgD3'
        b'hBCPtNaXicgFAEDEyDCMb7ZtfwSATUTsjOfimNCUUupVHMc3pJQTWmvzpIKIqDnnR67rfjZN'
        b'8ykifv9DkIiY1vpZFEXPoyiqjBc6BeQ4zmEul1syDOMlImokIjNN09e9Xu+h1trJmIyx2Lbt'
        b'0DRNwRhTAABpmppKKVsI4aVpesw1DCMuFovvGGNPMEmS92EY3k3TlGdChUJh37KsOE1TLqV0'
        b's9ENw1Cc84gxJpMkcfr9fiUTZoxJz/M2TSISRIQAAK7r/srn8wdCiHy327002kWGwWAAjLE4'
        b'n88flEqlH4PBoBxF0QUiQiJKkIgsKeWmUupqLpfrh2FYFUL45zHQtu2e53n7w+HQsyzrq2VZ'
        b'd7KlFADgQxAE16WUfrZJ27Z7nPO+aZoJAIBSypJSFoQQRSIyAAA454Hv+18A4D4iBsfbJKJK'
        b'HMef+v1+zTTNoe/7P7vdrt7Y2PBarZYNADA7Oyvm5ubCUqlkBEFwUSmVKxQKbcdxbiLi7t83'
        b'QDQVx/GW1nprZWVl1/f9FABoNHzfV6urq7ta6604jttEdOVUX4joarPZbCMijYtlgYjUbDbb'
        b'RHTtPF5DkiS3Go3G4eTkZLK+vr4TBEE7CIL22traTrlcThqNxmGSJLdPyv3niwjD8MHe3t6i'
        b'lNJdXl6eAABYWFg44pxH1Wp10fO8t+fqbhRENF+v13vZqPV6vUdE8/8tNIrt7e0XtVptOD09'
        b'HXU6naWz+Gd+AkRktFqtNwAAMzMzjxFRn8b/Da5HbfC6JwzbAAAAAElFTkSuQmCC'),

    # wifi_75 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAKxSURBVDiNlZS/S1tRFMfPffflvcT80EEjBUFaBxcT6Ga2QOiipUOh8KBTS1AQChb6Hzh0'
        b'sIOYQQdjtxoopRkc0kgLDv0DdKoJSehL8EeTpyZ5ycu978fplKAhxvYLZ/uezzmcc+4lMECI'
        b'GASAZ4yxl47jPEREDwAAIcQQBKEky/JXANgnhBT7c0kfaNqyrESn04lwzsccxxEHFSSEOJIk'
        b'XXs8np+iKL4hhPy+BURE6jjOW8Mw3hmGEewvNETodru1kZGRdUEQPhBCHIKIom3bu/V6/YXj'
        b'OO6uk1LakWW5KYoio5RaAAC2bYuWZcmMMb9t2z2vIAid0dHRz5TS18Q0zS/NZvOpbdtSF+Tz'
        b'+f64XK7O0dGRdHh46KlUKiIAwNTUlBWNRo1wOMxN03Truh7sgiml3O/37wPn/JOmabxaraKu'
        b'6xoinqTT6crc3JwBADgoQqGQkU6ny4h4ouu6Vq1WUdM0zjlPASK6GGPfWq3WKWMspyhK/S5Q'
        b'fyiKcs0Yy7VarTPO+XdElLvb9SFidmFhoQfzer328vLy5cHBgaqqakFV1UI2m1WXlpYuvV6v'
        b'3fUtLi7WEfEHIgZurwsxmEwmf1FKMRKJtEqlUqFWq+U3NzfP4/H4VTwev0okEue1Wi1fKpUK'
        b'8/PzLUop7u7u5hDxweAbQJze29vLtdvt3NbW1lkgEOh10o1AIGBtb2+f6bqeS6VSeUR8NPyw'
        b'EEOZTCZPCLlzdoQQzGQyeUR8PBTWlWmaUUVRtImJCTOZTJ42Go18o9HI7+zsnI6Pj5uKomim'
        b'aT4ZlHvni2g2m88vLi7WOOeejY2NMQCA1dXVa0mSjMnJyTW/35/6p+5uChFXYrFYb/OxWKyO'
        b'iCv/Dbqpcrn8fnZ2tj0zM2MUi8X1+/z3fgKIKBwfH38EAAiHw68IIc4w/1/FoaLg/smBjQAA'
        b'AABJRU5ErkJggg=='),

    # wifi_100 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AALBSURBVDiNlZK9SxtxGMefn2eikhc75JSiENqALslBN8UlErpoqVgIHnRqCIpOUUr/AQMd'
        b'uoiCOph0q8FSeohDmtBi4CaHgCFDk5A7vCS+NIkvF83bGZ9OCaFNrP3Cs32fz/NKoIUQsa9c'
        b'Lr8MBoOvY7HYE1mWewAAent7S0NDQ+L4+PhXrVa7RwgRWuU3g4w8z+86HI6swWBQAABbhVar'
        b'rc3MzOR5nt9FRGMrEJXNZt8uLS2dqlSqu3agP4OiqDuHw5HNZDLvELEDAIAgYmc0GvVOTU3Z'
        b'BUHorhexWCxlu91eYBimYjQabwEAjo6OOiORSNfOzo4uGo02vCaTqcxx3Gez2ewgBwcHX6an'
        b'p19kMhk1AADDMOX19fVfY2Nj5cPDQ3UoFOpJp9OdAACDg4O3Vqu1xDBMlef57vn5+b46eGBg'
        b'oMpx3B6Ew+FPNE1XAQAXFxfztVotxnFc2mw2l9qNarFYShzHpRRFiblcrjwAIE3T1XA47ANE'
        b'VO3v739zu93HlUolzrLs1UN3yLLsZaVSibvd7pNQKPQdEbvqR9EiYmBiYqIB02g0tbm5ufNg'
        b'MChJkpSUJCkZCASk2dnZc41GU6v7JicnrxDxByLq//o9j8fzk6IoHB0dvRFFMZnL5RKrq6un'
        b'Tqfzwul0XqytrZ3mcrmEKIrJkZGRG4qi0Ov1xhHxcds/3N7ejheLxfjGxsaJXq9vdFIPvV5/'
        b'u7m5eXJ9fR33+XwJRHzaEtYEtfj9/gQhpO3uCCHo9/sTiPjsXlhdiqJYWZbN0zSteDyeY1mW'
        b'E7IsJ7a2to4NBoPCsmxeUZTnrXJJO2ihUHh1dna2XK1We1ZWVh4BALhcrku1Wl3q7+9f1ul0'
        b'vgd11yxEXLDZbI3L22y2K0Rc+G9Qs1Kp1Pvh4eGiyWQqCYLw4V/+tiM3ddkRiUQ+AgAwDPOG'
        b'EHJ3n/83tSyizN1f7v0AAAAASUVORK5CYII='),

    # wifi_None =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAK0SURBVDiNnZS9axRRFMXvm3mZzWzixkG0VJQNEskWQUStBQsFsbHSRhtBERQC/gOCgnb2'
        b'+gdINIUIFikt04noJO7EsGrWSZ6787Hz5uPdY2EWNYb4cepzfpd37+EJ2kYA9hHRuTzPLzLz'
        b'QQAuEZEQIrMsK6jVas+I6LkQor01K7aADlRV9VBrfbIoit3MLLcbKIRgx3F6ruu+klLeEEJ8'
        b'+AUIwGbmW1mWzWZZtm/roB2E0dHRjXq9ft+yrAdCCBYApDHmUb/fv8DMo0Ons7BQyKNHY7l/'
        b'f2bbdkVEZIyR1eqqWy0u7ipOnXKGXsuy9MTExBPbtq9QWZZzSqk8DEOEYQilVKbn57uJlJw2'
        b'm8Wg3f6SJMl6kiTrg3b7S9psFomUrOfnu0qp7KdcXpblnAUgByCIiFzXVZ7nreLECYPpaWB5'
        b'ecScPr1Xr6zs0Z3OHnP27F4sL4/g8GHQsWOV53mrruuqzbUJACUBGMnz/GWapp8A+FEU9cMw'
        b'ROj7iFotJESIp6YQT00hIULUaiH0fYRhiCiKegD8NE0/F0WxAKA2PMo4ET2Nouh4URSN4SVr'
        b'SRJZZ86M4c2bESIiceRIyS9epPn4eAOARUTkOE7UaDQWiei8ECKyNsMJEV1yHOczEZGUcuB5'
        b'3kp9bEyR/NEcAKJeq331PG9FSjnYBHaJ6KIQIvq9A8ABrbXPzP6g0+lu9+S41eJBp9NlZl9r'
        b'vQTg0M7FAlp6be19NDPzHdBsYv31a6y/fftjj9PT0B8/tgHM/FVb9dWrs7GUiCcnOQuCNWZe'
        b'YualLAjW4slJjqVEfv367b+CDZXfvHmnDIJ3VVW14zhWcRyrqqraZRC8y2dn7/0TbCgA13q9'
        b'Xn9Y3l6v1wdw7b9gQxlj7iqlBhsbG5kx5v6f/H/8BABYxpjHRES2bV8WQvBO/m9mwNp1ZX6p'
        b'LgAAAABJRU5ErkJggg=='),

    # wifi_secure_0 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AALkSURBVDiNjZS/axxHFMffm5nduZ273ZOELF9nBVIKkjJXqFElZDAGIxDYbpJGIqmSQlLI'
        b'PxCSJg7GuMofEPID26RJIXDhRqQJCBcCH04h4h86KftzZnZmX4rcBukim3xhYBje+7yfDMIF'
        b'IqLLAHDNGHOzaZp3iKgDAICImjE2klL+BAAPEfHZtC9Oga44577VWg+ttTNN04iLAiJiE4bh'
        b'aRRFT4QQnyDi83NAIuJN03xWVdWnVVUtTAd6i6jT6Rwrpb5mjH2FiA0SkfDef5em6br3XraW'
        b'nHMtpcyEEIZz7gAAvPfCOSeNMbH3vtPaMsZ0v9//nnP+IdZ1/WOaplebpglbUK/XexkEgfbe'
        b'h9baqC2dMebCMKw457au606e5wstmDFmkyR5JBCxakuMomjc7XZfG2O6p6enV5xzEqZUFAUI'
        b'IUwURa9nZ2f/KIpivqqquX9aiwaJKLDWPnDOvaeUytM0vWytTf5PA6WUaRzHL8qyjIMgOAiC'
        b'4Go7lB4A/JCm6QctDBEbKeVfYRjmQogaAMA5F1hre8aYPhGxM9DfAOA6IqZi4pwT0S0p5WNr'
        b'bSKEKJMk+RMRSWvds9bGk/6abrc7VkqdZFk22N/fV3t7e8oY8+7y8vI3RPTRv3uGiK+IaBUA'
        b'fg3DELTWcVmWC20mrcqyvKSUejkajez6+rra2dl5Oh6PcWtr6/b8/Pzv54wR8bmU8kZd11gU'
        b'xWAaNmkPK4picHR0FK6urpbb29u3Nzc3vxwMBvz4+Pj9CxeYiIZZlj2s67qvlHolpcwBAIwx'
        b'vbIsL0kps93d3fjw8JBzznNE5MYYtba2lr5xgkR03Xt/4JwbZVl2kmXZiXNu5L0/IKKPl5aW'
        b'PADQ2bOxsXH0n5LOlP8zY+xOnudzWusZrfVMnudzjLE7APDLBHJO3nv/RuAEej+O47uc84ox'
        b'puM4voeI99/mc+FvclaMsS+SJFmY3D+fPDcrKysvFhcXz2U5HA7LvwF0n4N8B6195wAAAABJ'
        b'RU5ErkJggg=='),

    # wifi_secure_25 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAL1SURBVDiNjZO/a1xHEMdndve9vbf3KwqyfI3QCVIexGWuUCMOIWQwhnAgiN3kCkskhXEK'
        b'ScH/gEma4MIYFfkDRBKI06UQpHAj0oQTKQQ5LIOIf+gkvbv3Y/ftvkkRvSAfssjANst3PrPz'
        b'nVmES4KIrgPALa31Z3mezxNRCQAAEVPG2EBK+RMAPEPEvyZzcQI0Z619nKZp2xjzQZ7n4rKC'
        b'iJj7vn8aBMFzIcSXiPjiHSAR8TzPv0qS5EGSJDOTha4IKpVKx0qpbxlj3yBijkQknHPfh2HY'
        b'dc7JQsk5T6WUIyGE5pxbAADnnLDWSq111TlXKrSMsbRer+9wzj/HLMt+DMPwZp7nfgGqVCqv'
        b'Pc9LnXO+MSYoWmeMWd/3E865ybKsNB6PZwowY8zUarVfBCImRYtBEAzL5fJbrXX59PR0zlor'
        b'YSKiKAIhhA6C4O3U1NRhFEXTSZJ8+K+1qJGIPGPMz9baj5VS4zAMrxtjav/HQCllWK1WX8Vx'
        b'XPU8b9/zvJvFUCoA8EMYhp8UMETMpZRnvu+PhRAZAIC11jPGVLTWdSJiF6C/A8BtRAzFefKY'
        b'iO5IKX8zxtSEEHGtVvsbESlN04oxpnrury6Xy0Ol1MloNGrs7e2p3d1dpbX+aGFh4Tsi6v23'
        b'Z4j4hoiWAeBX3/chTdNqHMczxUuKiOP4mlLq9WAwMN1uV21ubv45HA5xfX397vT09B/viBHx'
        b'hZTy0yzLMIqixiTs3B4WRVHj6OjIX15ejjc2Nu6ura09ajQa/Pj4+MalC0xE7dFo9CzLsrpS'
        b'6o2UcgwAoLWuxHF8TUo52traqh4cHHDO+RgRudZarayshO+dIBHdds7t9/v9Qa/XO+n1eif9'
        b'fn/gnNsnoi9arZYDALp4VldXj67aCiCie51O56xI6HQ6Z0R0j4jmW62WnQR2u92Xl37+C54+'
        b'PTw8nFtaWrpvrcXt7e0niPiUiObfl3MlEABgdnb24c7OzgwAQLPZ/Pr8Ol9cXHzVbDbporbd'
        b'bsf/AIpXjhxwdWRBAAAAAElFTkSuQmCC'),

    # wifi_secure_50 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAMASURBVDiNjZPBSyRXEMarXr/unm6nZ1QSNx7EEfY4snjLHLzI4MGFsAeFgd5T5rCH5JBk'
        b'QWHZP0DZXEIYwqIQAt40CWZz8CJCkFwkCEl7WcEmBrLZZF21Z3q635vXr3LINrizrqSgLo/6'
        b'fkVVfQ/hiiCiGwDwgRDC11pPEFEBAAARU8ZYaNv29wDwBBGP+7XYBxpXSn2ZpmlNSjmoteZX'
        b'NUREbVnWueM4P3POP0bE318DEpGhtb6fJMlnSZKM9De6JqhQKJy6rvs5Y+wRImokIp5l2ddR'
        b'FC1kWWbnlYZhpLZttznnwjAMBQCQZRlXStlCCC/LskJeyxhLy+XyhmEYH2Kv1/suiqLbWmsr'
        b'BxWLxb9N00yzLLOklE4+OmNMWZaVGIYhe71eodPpjORgxpgslUo/ckRM8hEdx3k5MDDwQggx'
        b'cH5+Pq6UsqEv4jgGzrlwHOfF0NDQSRzH7yRJMvzfalEgEZlSyh+UUrdc1+1EUXRDSln6Pwu0'
        b'bTvyPO95t9v1TNM8NE3zdn6UIgB8G0XR+zkMEbVt2xeWZXU45z0AAKWUKaUsCiHKRMQuQX8B'
        b'gDuIGPFX4g4R3bVt+ycpZYlz3i2VSn+dnp7S2tpaMQgCDwBgcnJS+L7/cnh4+Kzdbr+3v7/v'
        b'7u7uukKIm9PT018QUfN1DxCNp2n6VGv9tNVqPfM8LwMAupye52WtVuvZwcHB2eDgIC0vL/+6'
        b'uLj42+joqNrb2/v0TWMRTW5vbx/1gy4nY4zW19fjRqMRE9Gt4+Pju1NTU7S1tfXNlQYmoprv'
        b'+092dnbKKysr/8zPz3eICDY3N4tLS0vv+r7fVkp5R0dHhmEYHUQ0hBDu3Nxc9NYLxnF8JwzD'
        b'wyAIwmazedZsNs+CIAjDMDxM0/SjarX6xjoajcaf19qCiO7V6/WLXFCv1y+I6B4RTVSrVdUP'
        b'XFhY+OPKz58HIj4+OTkZn52d/UQphaurq18h4mMimnib5logAMDY2NjDjY2NEQCASqXy4NWz'
        b'npmZeV6pVOhyba1W6/4L/PWaJGYWcMwAAAAASUVORK5CYII='),

    # wifi_secure_75 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAMYSURBVDiNfZPfSxxXFMfPvTPu7C6z6ktMBMX1reCIiA+yD4LIImihmwd/LEyfOkKU5qFt'
        b'QCH0D1Dat7CE4EMMaAR/BbFQCypYpE8+SDs+RIlDd5eYdhmtm5nduTN35vQlG+Jm9cB5uXzP'
        b'59x7zvcSqBGIeBcAvmKMqUEQtCNiGACAEOJQSg1Jkl4BwBYh5Ky6llSB2jjnTxzHSbiu2xgE'
        b'gVirISEkCIVC/0UikT9EUXxICPn7GhARhSAIHpXL5R/K5XJTdaNbAsPhsBmNRn+mlP5ECAkI'
        b'Ioq+7z8vFoujvu9LFaUgCI4kSe9FUWSCIHAAAN/3Rc65xBiL+b4frmgppU5DQ8OqIAjfEM/z'
        b'NorF4pdBEIQqIFmW/62rq3OOjo5C+/v7kXw+LwIAtLS08P7+/nJXV5freV7YsqymCphS6tbX'
        b'1/8CnPMl0zTdQqGAlmWZiPh6fX0939HR4QAA1kpFUZyNjY08Ir62LMssFApomqbLOX8JiFjH'
        b'GPvVtu23jLGTsbGxq5tA1Tk+Pn7FGDuxbfvcdd0dRJQq25UR8behoaGPMFmW/ampqYu9vb1s'
        b'Lpd7k8vl3uzs7GQnJycvZFn2K7pUKnWFiHuIWH/NNoh4Z2Fh4feJiYkvent7S8vLy+8ikQgu'
        b'LS3Juq5LAACdnZ1MVVXLtm2iadq9np6eqOd5nFJ63tfXt5tKpbTrHkBsW1lZOSmVSieZTOY8'
        b'Fov51c+MxWJ+JpM5Pzw8vGxsbMTZ2dk/p6en/2pubuYHBwfff24sxM7t7e3T22ZHKcXFxUU7'
        b'nU7biNh1dnb2dXd3N25ubr6oaWBETKiqurW7u9swNzdXGBkZsRAR1tbW5JmZmTuqqr7nnMdO'
        b'T08FQRAsQojAGIsODw8Xa/sfAGzbvm8YxrGu64amaZeapl3qum4YhnHsOM63iqJ8No50Ov32'
        b'RuCHmz5IJpMfN59MJq8Q8QEitiuKwquBo6OjuZqfvxKEkGfZbLZtcHDwO845mZ+ff0oIeYaI'
        b'7TfV3AoEAGhtbf1xdXW1CQAgHo8//nAcDAwM/BOPx/FTbSKRKP0PG+rOSt6exFMAAAAASUVO'
        b'RK5CYII='),

    # wifi_secure_100 =
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
        b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
        b'AAMtSURBVDiNjZLBSxtREMbnZbVq3aSCpK2iJHqx4JogHkRBCBIELTQ5mBjYXnQFDb3UHBRK'
        b'r4r+AbGIh1rQCkatqYVaUVGjFxEiyfYQpVlMYtSKitaku2bj9NAqolH6YC6Pb37vzfcNgRQH'
        b'EZ+IovhidnaWDQQCRaenp5kAACqVSiwpKREMBsMnlUo1TQgJpuq/DtJ4PJ7Pzc3NB7m5uQkA'
        b'wFSVnZ2dtFqthx6PZxoRNalA1P7+fqfD4dhLT0+/uAt0syiKumhpaTnY2dnpQkQFAABBxDS/'
        b'3//ebDZbgsFgxuUjOp1OtFgsv3Q6naTRaGQAgO3t7TSfz5fhcrmUPp8v81JbXFwsut1uF8Mw'
        b'LWRtbW3SbDY/j0ajDwAA9Hq92N/f/7O6ulrc2Nh4sLS0lBWJRNIAAAoKCmSDwfBbr9efr66u'
        b'Ztrt9sd+vz8TACA/P/98amrqC3i93hG1Wn0OAOhwOA6TyWRgYmIiUlpaKt41KsMw4uTkZCSR'
        b'SAQ6OjoOAQDVavW51+v9CIiYvri4+LW7uzsqSdKm1Wo9+V8Pm5qaTiRJ2uzp6dldXl6eQ8SM'
        b'y1BoRPxWX19/BaNpOmm3248WFhZC4XD4Rzgc/jE3Nxdqb28/omk6eakzmUwniLiAiCoAAHIt'
        b'afXQ0NBya2vrs8rKyvjo6OheVlYWjoyM0DzPZwAAlJWVSSzLnsViMcJx3NOKioqHiURCVigU'
        b'uzU1NfMmk4m7tYdjY2Ob8Xh80+l07iqVyuTNMZVKZdLpdO6ur68f5+TkYG9vr6+zs9Ofl5cn'
        b'r6ysdKTaybKZmZmt+7xTKBQ4PDwcs9lsMUTUB4PBl+Xl5eh2uz+QW8S/0CqWZafn5+cf9fX1'
        b'HTQ2Np4hIoyPj9NdXV1qlmV/ybKs3NraoiiKOiOEUJIkPWxoaDhNxQMAgFgsZhYE4TvP8wLH'
        b'ccccxx3zPC8IgvBdFMVXDMPcssNms0XvBP77aZvRaLxK3mg0niBiGyIWMQwj3wRaLJZw2n1A'
        b'QshAKBTS1NXVvZZlmQwODr4jhAwgYtFdPfcCAQAKCwvfulyuxwAAWq32zb/ri9ra2n2tVovX'
        b'tVVVVfE/yLPOKweLnlkAAAAASUVORK5CYII='),
    # wifi_secure_None =
    PyEmbeddedImage(
            b'iVBORw0KGgoAAAANSUhEUgAAABQAAAAQCAYAAAAWGF8bAAAABHNCSVQICAgIfAhkiAAAAAlw'
            b'SFlzAAAD6AAAA+gBtXtSawAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoA'
            b'AAM/SURBVDiNfVRPSBxnFH/vm3HHWTujS4itF6OwgZVdbQQPevAiwcAGSi/CQnNJe8ilFGxB'
            b'SumlN6G9BAklp1LIraQqpSkEQSjSiylCi5C4rmZHSNVx191vZnbmmz/f60G3Mdb44IPHx/v9'
            b'Hr/3ft+HcEEQ0bsA8IEQ4iMp5SARdQIAIGLAGNvVNG0RAH5BxJ3zWDxHdC2O44UgCCbCMOyR'
            b'UqoXNUREmUqlGrqu/6Gq6qeIWH2DkIgUKeUXvu9/7vt+7/lGlwR1dnbW0un0d4yxbxFRIhGp'
            b'SZL8wDmfSZJEa1emVlZCdWzMUfv7fUVRYgCAJEnU2LL0+NkzI7x5M9WuZYwF3d3dPymK8jFE'
            b'UfRzrVYTtm2TbdtUr9f9YGnpwFVV2cpmw1alcui67pHruketSuWwlc2GrqrKYGnpoF6v+21c'
            b'rVYTURQ9ZojotyXqul7PZDIWjY8nslAAub3dkdy6dTV4+fJKsLd3Jbl9+6rc3u6gXA5obCzJ'
            b'ZDKWruv116NFAUTUIYT4zfO8V0S01Ww2m7Ztk10uEx8ZIReAnFyOnFyOXADiIyNkl8tk2zZx'
            b'zptEtOV53j9hGK4QkdZeyjsA8JhzPh6GodnepOZ5nBWLXbS52QEAgPl8JJ888URXl0lEDABA'
            b'0zRuGMafAPAhInL1FOwS0R1N034Pw9BUVbVlmuY+SIkBY13/rVRKTKdSjXQmU3cc57319fX0'
            b'6upqWgiRnZycvE9En7zpAaJrQRBsSSm3vGr1gOfzJzKHhogPDZ3k+Tx51erBxsbGcU9PD83P'
            b'z/81Nzf3d19fX7y2tjb7f2MRDYv9/Qq/ceNkftev09HmJh09f/6adHiYfl1cbJVKJY+I3t/Z'
            b'2bkzOjpKy8vLP15o4ODu3c+iR4/uw+AgqU+fHmr9/RwAQFiWGU9P9zIi/HJ6OilXKkxRFBcR'
            b'FSFEulgs8rc+ATE7+01kWS/iON51HOfYcZzjOI53I8t6ES4sPCgUCgkA0NlTKpVevZXwVP69'
            b'RqPRbJu30Wg0iegeEQ0WCoX4POHMzMweu4wQER8ahvFAURSfMRYYhvE9Ij68DHPhb3I2GGNf'
            b'm6bZe5p/dXotp6amDgYGBuhs7cTEROtf0HryiKJqkboAAAAASUVORK5CYII='),
)


connection_bt = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAnXAAAJ1wGxbhe3'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAALRJREFUOI3F0q+KQlEQ'
    b'x/GPesNi0Ocw+QLb3GY22barcIvVIBuM+wIGg09hs4kYNgh2k0FEMIkYvEnun4PB/cKEw/md'
    b'38yZGf6bSsF9jAY2ryaY4opulqAcYDJJohNqUMMIH8l5hwFmqD+LoxSDi8e/FzjiE230cQqo'
    b'GJQwxi0x+coShvQgl7QxRpijiT+sMMQZ65AKqtiihQOW6OFXShOLmOIHexljDDHIXaQiYny/'
    b'+vg93AExzxyNYgpTgwAAAABJRU5ErkJggg==')

#----------------------------------------------------------------------
connection_msd = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAnXAAAJ1wGxbhe3'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAN5JREFUOI3F0rFKQ0EQ'
    b'heFPYuU7mFYFfQBDEBKw0MpeC4O1tU+Ryk4bU5hatBKtFXtBkWCVJ4iIKAgWzr0sN7nJ7XJg'
    b'4TCz52d2GeathQm1dayV3H/B8zTAHk7xWALYxDGuJjUXMUCzJCx6g7g7pg7upoQz3eOwWKzh'
    b'DVsVAI10imyUA3xiN84sfWAfvQzQxjfOKoShFZkc8IUbvMcEXQwLoTpWwl9jOX3CD0bhl3CJ'
    b'fgFwkfhRZHLAr/+PhFds46QAeEp8LTL5Iu3gHA+qqYEj3KabuIHVioCxlZ6f/gDThycMg2u2'
    b'iAAAAABJRU5ErkJggg==')

#----------------------------------------------------------------------
connection_usb = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAnXAAAJ1wGxbhe3'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAQZJREFUOI210k0rRVEU'
    b'BuDn+iiSgcvEZzER5UZ+hamZv8BAGZCBoV9gaE5JMmJGKQZuilJKojA28G10Dfa5um3nnHTL'
    b'O9rttda71rvexT9jFDtoqKe4B/f4xHpWUmMOwSBe0Y0yWjGNSZxmFbVgHrNoRgkXSewQG3hH'
    b'Z7WgKSJYxXBC1IXdKF5CAZXqR7ycPhzhBANRbBlFrOApS8IIrnGJoUhCPx4EZ34QS7jCNl5w'
    b'i3F04ABj2MJdHgE8Yw69eEQ71rCHr6zRa1FIOi8mUt4EK1ORdmEVnAtH1IYzwffiX7rXYhMz'
    b'yXsfU2lJaTuo4hgLghsTyVS/kHfKZXwI9i3hJnfeevEN+D8u1kgi0SMAAAAASUVORK5CYII=')

#----------------------------------------------------------------------
connection_wifi = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAnXAAAJ1wGxbhe3'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAJlJREFUOI3t0bEKwXEU'
    b'xfGPKGVTbB7AKjyCycBmJrzCf+J9lGJgMtpt3sAiu9ngKumH7L7Tr3POvZ3ujz+5hFZCFx3U'
    b'Qjthhy2uz+H8y/AAGzRxwB5HFDFGFsuOqTYZzuh9aNyPTJYyF6jHu4p5VN5ihkp49ci+pY0L'
    b'VhhihHVorU+DD5aYJPRpeD/RcD/oWwpfFpSlv/rPEze37hjRQSs+hQAAAABJRU5ErkJggg==')

