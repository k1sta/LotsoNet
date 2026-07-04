def main():
    num = 100
    acc = 0
    for i in range(1,num):
        for j in range(1,num):
            for k in range(1,num):
                acc +=(k+i+j)/(i**0.5)
    return {"nice":acc,"other":acc-1}